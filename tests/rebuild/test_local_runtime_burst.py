"""Entry scripts survive a burst queued behind an occupied accept loop."""
import http.client
import threading

from deck_master import local_runtime


def test_pending_thumbnail_and_entry_connections_do_not_reset(created_store):
    desc = local_runtime.descriptor(project=created_store.project_root)
    server, _ = local_runtime.bind_server(desc)
    connections = []
    failures = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    try:
        # Six image connections can overlap the document, styles and scripts.
        # Hold acceptance until the burst has arrived, without mocking TCP.
        for _ in range(12):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=1)
            connections.append(connection)
            try:
                connection.connect()
            except OSError as error:
                failures.append(str(error))
        thread.start()
        assert not failures, failures
        expected = (local_runtime._PACKAGE / "resources/static/v2/app.js").read_bytes()
        for connection in connections:
            connection.request("GET", "/v2/app.js")
        for connection in connections:
            response = connection.getresponse()
            assert response.status == 200
            assert response.read() == expected
    finally:
        for connection in connections:
            connection.close()
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=2)
        server.server_close()
