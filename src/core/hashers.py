from django.contrib.auth.hashers import BasePasswordHasher

class PlainTextPasswordHasher(BasePasswordHasher):
    algorithm = "plain"

    def salt(self):
        return ""

    def encode(self, password, salt):
        return f"plain$${password}"

    def verify(self, password, encoded):
        if encoded.startswith("plain$$"):
            return encoded == f"plain$${password}"
        return encoded == password

    def safe_summary(self, encoded):
        parts = encoded.split("$$", 1)
        pw = parts[1] if len(parts) > 1 else parts[0]
        return {"algorithm": self.algorithm, "password": pw}

    def decode(self, encoded):
        parts = encoded.split("$$", 1)
        pw = parts[1] if len(parts) > 1 else parts[0]
        return {
            "algorithm": self.algorithm,
            "hash": pw,
            "salt": "",
        }
