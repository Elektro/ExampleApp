# -*- coding: utf-8 -*-

import speakap


SPEAKAP_APP_ID = "000a000000000005"
SPEAKAP_APP_SECRET = "suppl13s!!!"

speakap_api = speakap.API({
    "scheme": "https",
    "hostname": "api.speakap.io",
    "app_id": SPEAKAP_APP_ID,
    "app_secret": SPEAKAP_APP_SECRET
})
