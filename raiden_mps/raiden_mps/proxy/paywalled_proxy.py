import gevent

import os
from gevent import monkey


monkey.patch_all()
from flask import Flask
from flask_restful import (
    Api,
)

from raiden_mps.channel_manager import (
    ChannelManager
)

from raiden_mps.proxy.resources import (
    Expensive,
    ChannelManagementAdmin,
    ChannelManagementListChannels,
    ChannelManagementChannelInfo,
    ChannelManagementRoot,
    StaticFilesServer
)

from raiden_mps.proxy.content import PaywallDatabase
from raiden_mps.proxy.resources.expensive import LightClientProxy
from raiden_mps.config import API_PATH


import logging

log = logging.getLogger(__name__)

RAIDEN_MPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
HTML_DIR = os.path.join(RAIDEN_MPS_DIR, 'raiden_mps', 'webui')
JSLIB_DIR = os.path.join(HTML_DIR, 'js')


class PaywalledProxy:
    def __init__(self,
                 channel_manager,
                 flask_app=None,
                 paywall_html_dir=HTML_DIR):
        if not flask_app:
            self.app = Flask(__name__)
        else:
            assert isinstance(flask_app, Flask)
            self.app = flask_app
        assert isinstance(channel_manager, ChannelManager)
        assert isinstance(paywall_html_dir, str)
        self.paywall_db = PaywallDatabase()
        self.api = Api(self.app)
        self.rest_server = None
        self.server_greenlet = None

        self.channel_manager = channel_manager
        self.channel_manager.start()

        cfg = {
            'contract_address': channel_manager.state.contract_address,
            'receiver_address': channel_manager.receiver,
            'channel_manager': self.channel_manager,
            'paywall_db': self.paywall_db,
            'light_client_proxy': LightClientProxy(paywall_html_dir + "/index.html")
        }
        self.api.add_resource(StaticFilesServer, "/js/<path:content>",
                              resource_class_kwargs={'directory': JSLIB_DIR})
        self.api.add_resource(Expensive, "/<path:content>", resource_class_kwargs=cfg)
        self.api.add_resource(ChannelManagementChannelInfo,
                              API_PATH + "/channels/<string:sender_address>/<int:opening_block>",
                              resource_class_kwargs={'channel_manager': self.channel_manager})
        self.api.add_resource(ChannelManagementAdmin,
                              API_PATH + "/admin",
                              resource_class_kwargs={'channel_manager': self.channel_manager})
        self.api.add_resource(ChannelManagementListChannels,
                              API_PATH + "/channels/",
                              API_PATH + "/channels/<string:sender_address>",
                              resource_class_kwargs={'channel_manager': self.channel_manager})
        self.api.add_resource(ChannelManagementRoot, "/cm")

    def add_content(self, content):
        self.paywall_db.add_content(content)

    def run(self, debug=False):
        gevent.get_hub().SYSTEM_ERROR += (BaseException, )
        self.channel_manager.wait_sync()
        from gevent.wsgi import WSGIServer
        self.rest_server = WSGIServer(('localhost', 5000), self.app)
        self.server_greenlet = gevent.spawn(self.rest_server.serve_forever)

    def stop(self):
        assert self.rest_server is not None
        assert self.server_greenlet is not None
        # we should stop the server only if it has been started. In case we do stop()
        #  right after start(), the server may be in an undefined state and join() will
        #  hang indefinetely (this often happens with tests)
        for try_n in range(5):
            if self.rest_server.started is True:
                break
            gevent.sleep(1)
        self.rest_server.stop()
        self.server_greenlet.join()

    def join(self):
        self.server_greenlet.join()
