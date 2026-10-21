"""Stop must wake select, then close sockets on the event-loop thread."""
from threading import Event, Thread, get_ident
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from waitress import create_server, wasyncore
from songranker.hosting import register_waitress_shutdown


class WaitressShutdownTests(unittest.TestCase):
    def test_cleanup_runs_on_loop_thread_for_single_and_multiple_listeners(self):
        for listen in ('127.0.0.1:0', '127.0.0.1:0 127.0.0.1:0'):
            with self.subTest(listen=listen):
                server = create_server(lambda environ, start: [], listen=listen,
                                       asyncore_loop_timeout=30, threads=1)
                coordinator = SimpleNamespace()
                register_waitress_shutdown(server, coordinator)
                entered_select = Event()
                closed_on = []
                errors = []
                real_select = wasyncore.select.select
                real_close = wasyncore.close_all

                def selecting(*args):
                    entered_select.set()
                    return real_select(*args)

                def closing(*args):
                    closed_on.append(get_ident())
                    return real_close(*args)

                def run():
                    try:
                        server.run()
                    except BaseException as error:
                        errors.append(error)

                loop = Thread(target=run, daemon=True)
                with patch.object(wasyncore.select, 'select', selecting), \
                     patch.object(wasyncore, 'close_all', closing):
                    try:
                        loop.start()
                        self.assertTrue(entered_select.wait(3))
                        coordinator.shutdown()
                        loop.join(3)
                        self.assertFalse(loop.is_alive(), 'Shutdown failed to wake select')
                        self.assertEqual(errors, [])
                        self.assertEqual(closed_on, [loop.ident])
                    finally:
                        server.task_dispatcher.shutdown()
                        socket_map = getattr(server, 'map', None)
                        if socket_map is None:
                            socket_map = server._map
                        real_close(socket_map)

    def test_unexpected_socket_error_is_not_suppressed(self):
        server = create_server(lambda environ, start: [], host='127.0.0.1', port=0)
        register_waitress_shutdown(server, SimpleNamespace())
        error = OSError(10038, 'not a socket')
        try:
            with patch.object(wasyncore.select, 'select', side_effect=error):
                with self.assertRaises(OSError) as caught:
                    server.run()
            self.assertIs(caught.exception, error)
        finally:
            server.task_dispatcher.shutdown()
            wasyncore.close_all(server._map)


if __name__ == '__main__':
    unittest.main()
