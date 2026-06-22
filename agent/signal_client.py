import asyncio
import base64
import logging
import mimetypes
import os

import httpx

logger = logging.getLogger(__name__)

MAX_SIGNAL_MESSAGE_LENGTH = 4000


class SignalClient:
    def __init__(self, api_url: str, phone_number: str):
        self.api_url = api_url
        self.phone_number = phone_number
        self.client = httpx.AsyncClient(base_url=api_url, timeout=30)
        self._not_registered_logged = False

    async def close(self):
        await self.client.aclose()

    async def receive(self) -> list[dict]:
        try:
            resp = await self.client.get(f"/v1/receive/{self.phone_number}")
            if resp.status_code == 400:
                if not self._not_registered_logged:
                    logger.warning(
                        "Signal number %s not registered. "
                        "Run './deploy.sh link' to link your device.",
                        self.phone_number,
                    )
                    self._not_registered_logged = True
                return []
            self._not_registered_logged = False
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            logger.warning("Signal API not reachable, retrying...")
            return []
        except httpx.TimeoutException:
            logger.warning("Signal API timeout on receive")
            return []
        except Exception:
            logger.exception("Error receiving messages")
            return []

    async def send(self, recipient: str, message: str):
        chunks = self._split_message(message)
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(0.3)
            try:
                resp = await self.client.post(
                    "/v2/send",
                    json={
                        "message": chunk,
                        "number": self.phone_number,
                        "recipients": [recipient],
                    },
                )
                resp.raise_for_status()
            except Exception:
                logger.exception("Error sending message to %s", recipient)

    async def send_file(self, recipient: str, file_path: str, message: str = ""):
        """Send a file as a Signal attachment via /v2/send (JSON base64_attachments).

        Raises on failure so callers (the send_file tool) can report it.
        """
        filename = os.path.basename(file_path)
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        # signal-cli-rest-api accepts a data-URI form with an optional filename.
        attachment = f"data:{mime};filename={filename};base64,{b64}"
        resp = await self.client.post(
            "/v2/send",
            json={
                "number": self.phone_number,
                "recipients": [recipient],
                "message": message or "",
                "base64_attachments": [attachment],
            },
            timeout=120,
        )
        resp.raise_for_status()
        logger.info("File sent to %s: %s (%s)", recipient, filename, mime)

    async def download_attachment(self, attachment_id: str, save_dir: str = "/tmp") -> str | None:
        try:
            resp = await self.client.get(f"/v1/attachments/{attachment_id}")
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "application/octet-stream")
            ext = _mime_to_ext(content_type)
            file_path = os.path.join(save_dir, f"attachment_{attachment_id}{ext}")
            with open(file_path, "wb") as f:
                f.write(resp.content)
            logger.info(
                "Downloaded attachment %s to %s (%d bytes)",
                attachment_id, file_path, len(resp.content),
            )
            return file_path
        except Exception:
            logger.exception("Error downloading attachment %s", attachment_id)
            return None

    async def is_registered(self) -> bool:
        try:
            resp = await self.client.get("/v1/about", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def _split_message(self, message: str) -> list[str]:
        if len(message) <= MAX_SIGNAL_MESSAGE_LENGTH:
            return [message]

        chunks = []
        remaining = message
        while remaining:
            if len(remaining) <= MAX_SIGNAL_MESSAGE_LENGTH:
                chunks.append(remaining)
                break

            split_at = remaining.rfind("\n\n", 0, MAX_SIGNAL_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = remaining.rfind("\n", 0, MAX_SIGNAL_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = remaining.rfind(" ", 0, MAX_SIGNAL_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = MAX_SIGNAL_MESSAGE_LENGTH

            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")

        return chunks


def _mime_to_ext(content_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "application/json": ".json",
    }
    for mime, ext in mapping.items():
        if mime in content_type:
            return ext
    return ".bin"


def encode_image_base64(file_path: str) -> tuple[str, str] | None:
    try:
        ext = os.path.splitext(file_path)[1].lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(ext)
        if not media_type:
            return None
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return media_type, data
    except Exception:
        logger.exception("Error encoding image: %s", file_path)
        return None
