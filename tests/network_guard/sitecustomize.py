"""Inherited by demo subprocesses during tests; fail any Python socket creation."""
import socket


def blocked(*args, **kwargs):
    raise RuntimeError('Network disabled in test subprocess')


socket.socket = blocked
socket.create_connection = blocked
