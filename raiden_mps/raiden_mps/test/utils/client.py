from raiden_mps.client import Channel
from raiden_mps import Client
from raiden_mps.test.config import TEST_RECEIVER_PRIVKEY
from raiden_mps.crypto import sign_balance_proof, privkey_to_addr


def close_all_channels(client: Client):
    close_events = [c.close() for c in client.channels if c.state == Channel.State.open]
    assert all(close_events)


def close_channel_cooperatively(
        channel, privkey_receiver: str=TEST_RECEIVER_PRIVKEY, balance: int=None
):
    if balance is not None:
        channel.balance = balance
    closing_sig = sign_balance_proof(
        privkey_receiver, channel.receiver, channel.block,
        channel.balance if balance is None else balance
    )
    assert channel.close_cooperatively(closing_sig)


def close_all_channels_cooperatively(
        client: Client, privkey_receiver: str=TEST_RECEIVER_PRIVKEY, balance: int=None
):
    receiver_addr = privkey_to_addr(privkey_receiver)
    client.sync_channels()
    channels = [
        c for c in client.channels if c.state != Channel.State.closed and
                                      c.receiver == receiver_addr
    ]
    for channel in channels:
        close_channel_cooperatively(channel, privkey_receiver, balance)
