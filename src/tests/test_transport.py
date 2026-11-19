import unittest
from unittest.mock import patch, MagicMock

from printer.transport import (
    NetworkTransport
)
from errors import TransportError

from printer.transport_config import TransportConfig


class TestNetworkTransport(unittest.TestCase):

    def setUp(self):
        self.config = TransportConfig(
            transport_type="network",
            host="192.168.1.100",
            port=9100,
            timeout=5,
        )

        self.transport = NetworkTransport(self.config)

    @patch("printer.transport.socket.create_connection")
    def test_successful_send(self, mock_connection):
        mock_socket = MagicMock()
        mock_connection.return_value = mock_socket

        data = b"\x1B\x40HELLO\n"

        result = self.transport.send(data)

        mock_connection.assert_called_once_with(
            ("192.168.1.100", 9100),
            timeout=5,
        )

        mock_socket.sendall.assert_called_once_with(data)

        mock_socket.close.assert_called_once()

        self.assertEqual(result, len(data))

    @patch("printer.transport.socket.create_connection")
    def test_connection_failure(self, mock_connection):
        mock_connection.side_effect = OSError(
            "Connection refused"
        )

        with self.assertRaises(TransportError):
            self.transport.send(b"HELLO")

    @patch("printer.transport.socket.create_connection")
    def test_send_failure(self, mock_connection):
        mock_socket = MagicMock()

        mock_connection.return_value = mock_socket

        mock_socket.sendall.side_effect = OSError(
            "Network error"
        )

        with self.assertRaises(TransportError):
            self.transport.send(b"HELLO")

        mock_socket.close.assert_called_once()

    def test_empty_data(self):
        with self.assertRaises(TransportError):
            self.transport.send(b"")

    def test_invalid_data_type(self):
        with self.assertRaises(TypeError):
            self.transport.send("HELLO")

    def test_invalid_transport_type(self):
        config = TransportConfig(
            transport_type="USB",
            device="USB001",
        )

        with self.assertRaises(TransportError):
            NetworkTransport(config)

    def test_missing_host(self):
        config = TransportConfig(
            transport_type="network",
            host=None,
            port=9100,
        )

        with self.assertRaises(TransportError):
            NetworkTransport(config)

    def test_invalid_port(self):
        config = TransportConfig(
            transport_type="network",
            host="192.168.1.100",
            port=70000,
        )

        with self.assertRaises(TransportError):
            NetworkTransport(config)

    def test_invalid_timeout(self):
        config = TransportConfig(
            transport_type="network",
            host="192.168.1.100",
            port=9100,
            timeout=0,
        )

        with self.assertRaises(TransportError):
            NetworkTransport(config)


if __name__ == "__main__":
    unittest.main()
