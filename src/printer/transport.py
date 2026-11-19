
import socket

from printer.transport_config import TransportConfig

from errors import TransportError

class NetworkTransport:

    def __init__(self, config: TransportConfig):
        self.config = config

        if config.transport_type != "network":
            raise TransportError(
                "NetworkTransport requires transport_type='network'."
            )

        if not config.host:
            raise TransportError(
                "Printer host address is required."
            )

        if config.port is None or not 1 <= config.port <= 65535:
            raise TransportError(
                "Printer port must be between 1 and 65535."
            )

        if config.timeout <= 0:
            raise TransportError(
                "Connection timeout must be greater than zero."
            )

    def send(self, data: bytes) -> int:
        """
        Send raw bytes to a network printer.

        Returns the number of bytes submitted successfully.
        This does not confirm that the printer physically printed them.
        """

        if not isinstance(data, bytes):
            raise TypeError("Printer data must be bytes.")

        if not data:
            raise TransportError(
                "Cannot send an empty receipt."
            )

        connection = None

        try:
            connection = socket.create_connection(
                (self.config.host, self.config.port),
                timeout=self.config.timeout,
            )

            connection.sendall(data)

            return len(data)

        except OSError as error:
            raise TransportError(
                f"Failed to send data to printer "
                f"{self.config.host}:{self.config.port}: {error}"
            ) from error

        finally:
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    pass
