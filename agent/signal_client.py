import logging
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

    def receive(self) -> list[dict]:
        try:
            resp = self.session.get(
                f"{self.api_url}/v1/receive/{self.phone_number}",
                timeout=30,
            )
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
