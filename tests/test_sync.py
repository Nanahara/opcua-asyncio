import time
from concurrent.futures import Future

import pytest

from asyncua.sync import Client, Server, ThreadLoop, Node
from asyncua import ua, uamethod


@uamethod
def divide(parent, x, y):
    return x / y


@pytest.fixture
def server():
    s = Server()
    s.set_endpoint('opc.tcp://0.0.0.0:8840/freeopcua/server/')
    uri = "http://examples.freeopcua.github.io"
    idx = s.register_namespace(uri)
    myobj = s.nodes.objects.add_object(idx, "MyObject")
    myvar = myobj.add_variable(idx, "MyVariable", 6.7)
    mysin = myobj.add_variable(idx, "MySin", 0, ua.VariantType.Float)
    meth = s.nodes.objects.add_method(idx, "Divide", divide, [ua.VariantType.Float, ua.VariantType.Float], [ua.VariantType.Float])
    with s:
        yield s


@pytest.fixture
def tloop():
    with ThreadLoop() as t_loop:
        yield t_loop


@pytest.fixture
def client(tloop, server):
    c = Client("opc.tcp://admin@localhost:8840/freeopcua/server")
    with c:
        yield c


@pytest.fixture
def idx(client):
    uri = "http://examples.freeopcua.github.io"
    i = client.get_namespace_index(uri)
    return i


def test_sync_client(client, idx):
    client.load_type_definitions()
    myvar = client.nodes.root.get_child(["0:Objects", f"{idx}:MyObject", f"{idx}:MyVariable"])
    assert myvar.get_value() == 6.7


def test_sync_get_node(client):
    node  = client.get_node(85)
    assert node == client.nodes.objects
    nodes = node.get_children()
    assert len(nodes) > 2
    assert nodes[0] == client.nodes.server
    assert isinstance(nodes[0], Node)


class MySubHandler():

    def __init__(self):
        self.future = Future()

    def reset(self):
        self.future = Future()

    def datachange_notification(self, node, val, data):
        self.future.set_result((node, val))

    def event_notification(self, event):
        self.future.set_result(event)


def test_sync_sub(client):
    myhandler = MySubHandler()
    sub = client.create_subscription(1, myhandler)
    var = client.nodes.objects.add_variable(3, 'SubVar', 0.1)
    sub.subscribe_data_change(var)
    n, v = myhandler.future.result()
    assert v == 0.1
    assert n == var
    myhandler.reset()
    var.set_value(0.123)
    n, v = myhandler.future.result()
    assert v == 0.123
    sub.delete()


def test_sync_meth(client, idx):
    res = client.nodes.objects.call_method(f"{idx}:Divide", 4, 2)
    assert res == 2
    with pytest.raises(ua.UaError):
        res = client.nodes.objects.call_method(f"{idx}:Divide", 4, 0)


