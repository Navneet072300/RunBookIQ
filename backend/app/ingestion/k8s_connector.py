"""
Kubernetes event watcher connector.

Streams events.v1 from the K8s API server using the kubernetes Python SDK.
Supports both in-cluster (service account) and kubeconfig authentication.
"""
import asyncio
from typing import AsyncGenerator, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)


def _load_kube_client():
    """Load kubernetes client; in-cluster if no kubeconfig specified."""
    try:
        from kubernetes import client, config, watch

        if settings.k8s_kubeconfig:
            config.load_kube_config(config_file=settings.k8s_kubeconfig)
            log.info("k8s_auth", method="kubeconfig", path=settings.k8s_kubeconfig)
        else:
            config.load_incluster_config()
            log.info("k8s_auth", method="in_cluster")
        return client, watch
    except Exception as exc:
        log.error("k8s_load_config_failed", error=str(exc))
        raise


async def stream_k8s_events(
    namespace: Optional[str] = None,
    resource_version: str = "",
) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields raw K8s event dicts.
    Runs the synchronous watch in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    def _watch_blocking():
        try:
            client_mod, watch_mod = _load_kube_client()
            v1 = client_mod.CoreV1Api()
            w = watch_mod.Watch()
            ns = namespace or settings.k8s_namespace

            log.info("k8s_watch_start", namespace=ns)
            for event in w.stream(
                v1.list_namespaced_event,
                namespace=ns,
                resource_version=resource_version,
                timeout_seconds=0,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, event["object"].to_dict())
        except Exception as exc:
            log.error("k8s_watch_error", error=str(exc))
            loop.call_soon_threadsafe(queue.put_nowait, None)

    asyncio.get_event_loop().run_in_executor(None, _watch_blocking)

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event


async def start_k8s_watcher(ingest_callback, namespace: Optional[str] = None) -> None:
    """
    Background task: watches K8s events and calls ingest_callback for each.
    Reconnects on error with exponential backoff.
    """
    backoff = 1
    while True:
        try:
            log.info("k8s_watcher_starting", namespace=namespace)
            async for raw_event in stream_k8s_events(namespace=namespace):
                try:
                    await ingest_callback(raw_event, source="kubernetes")
                except Exception as exc:
                    log.error("k8s_event_callback_error", error=str(exc))
            backoff = 1
        except Exception as exc:
            log.error("k8s_watcher_error", error=str(exc), backoff=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
