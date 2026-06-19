import base64
import logging
import os
import time
import requests

logger = logging.getLogger(__name__)

MAX_SIGNAL_MESSAGE_LENGTH = 4000


class SignalClient:
    def __init__(self, api_url: str, phone_number: str):
        self.api_url = api_url
        self.phone_number = phone_number
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._not_registered_logged = False

    def receive(self) -> list[dict]:
        try:
            resp = self.session.get(
                f"{self.api_url}/v1/receive/{self.phone_number}",
                timeout=30,
            )
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
        except requests.exceptions.ConnectionError:
            logger.warning("Signal API not reachable, retrying...")
            return []
        except requests.exceptions.Timeout:
            logger.warning("Signal API timeout on receive")
            return []
        except Exception:
            logger.exception("Error receiving messages")
            return []

    def send(self, recipient: str, message: str):
        chunks = self._split_message(message)
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.3)
            try:
                resp = self.session.post(
                    f"{self.api_url}/v2/send",
                    json={
                        "message": chunk,
                        "number": self.phone_number,
                        "recipients": [recipient],
                    },
                    timeout=30,
                )
                resp.raise_for_status()
            except Exception:
                logger.exception("Error sending message to %s", recipient)

    def send_file(self, recipient: str, file_path: str, message: str = ""):
        try:
            with open(file_path, "rb") as f:
                filename = os.path.basename(file_path)
                resp = requests.post(
                    f"{self.api_url}/v2/send",
                    data={
                        "number": self.phone_number,
                        "recipients": recipient,
                        "message": message,
                    },
                    files={"attachments": (filename, f)},
                    timeout=60,
                )
                resp.raise_for_status()
                logger.info("File sent to %s: %s", recipient, filename)
        except Exception:
            logger.exception("Error sending file to %s", recipient)

    def download_attachment(self, attachment_id: str, save_dir: str = "/tmp") -> str | None:
        try:
            resp = self.session.get(
                f"{self.api_url}/v1/attachments/{attachment_id}",
                timeout=30,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            ext = _mime_to_ext(content_type)
            file_path = os.path.join(save_dir, f"attachment_{attachment_id}{ext}")
            with open(file_path, "wb") as f:
                f.write(resp.content)
            logger.info("Downloaded attachment %s to %s (%d bytes)", attachment_id, file_path, len(resp.content))
            return file_path
        except Exception:
            logger.exception("Error downloading attachment %s", attachment_id)
            return None

    def is_registered(self) -> bool:
        try:
            resp = self.session.get(
                f"{self.api_url}/v1/about",
                timeout=10,
            )
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
