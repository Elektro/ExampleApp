# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import httplib
import json
import logging

try:
    from google.appengine.api import urlfetch
except ImportError:
    urlfetch = None

from urllib import quote


SPEAKAP_API_HOST = "api.speakap.io"


#
# Generates the signed request string from the parameters
#
# @param params Object containing POST parameters passed during the signed request
#
# @return Query string containing the parameters of the signed request.
#
# The result of this method may be passed into validate_signature() instead of the original
# parameters.
#
def signed_request(params):
    keys = params.keys()
    keys.sort()
    query_string = "&".join(quote(key, "~") + "=" + quote(params[key], "~") for key in keys)
    return query_string


#
# Speakap API wrapper
#
# You should instantiate the Speakap API as follows:
#s
#   import speakap
#   speakap_api = speakap.API(MY_APP_ID, MY_APP_SECRET)
#
# Obviously, MY_APP_ID and MY_APP_SECRET should be replaced with your actual App ID and secret (or
# be constants containing those).
#
# After you have instantiated the API wrapper, you can perform API calls as follows:
#
#   (json_result, error) = speakap_api.get("/networks/%s/user/%s/" % (network_eid, user_eid))
#
#   (json_result, error) = speakap_api.post("/networks/%s/messages/" % network_eid, {
#       "body": "test 123",
#       "messageType": "update",
#       "recipient": { "type": "network", "EID": network_eid }
#   })
#
# The JSON result contains the already parsed reply in case of success, but is None in case of an
# error. The error variable is None in case of success, but is an object containing code and message
# properties in case of an error.
#
# WARNING: If you use this class to make requests on any other platform than Google App Engine,
#          the SSL certificate of the Speakap API service is not confirmed, leaving you vulnerable
#          to man-in-the-middle attacks. This is due to a limitation of the SSL support in the
#          Python framework. You are strongly advised to take your own precautions to make sure
#          the certificate is valid.
#
class API:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = "%s_%s" % (app_id, app_secret)

    #
    # Performs a DELETE request to the Speakap API
    #
    # @param path The path of the REST endpoint, including optional query parameters.
    #
    # @return A tuple containing the parsed JSON reply (in case of success) and an error object
    #         (in case of an error).
    #
    # Example:
    #
    #   (json_result, error) = speakap_api.delete("/networks/%s/messages/%s/" % (network_eid, message_eid))
    #   if json_result:
    #       ... do something with json_result ...
    #   else
    #       ... do something with error ...
    #
    def delete(self, path):
        response = self._request("DELETE", path)
        return self._handle_response(response)

    #
    # Performs a GET request to the Speakap API
    #
    # @param path The path of the REST endpoint, including optional query parameters.
    #
    # @return A tuple containing the parsed JSON reply (in case of success) and an error object
    #         (in case of an error).
    #
    # Example:
    #
    #   (json_result, error) = speakap_api.get("/networks/%s/timeline/?embed=messages.author" % network_eid)
    #   if json_result:
    #       ... do something with json_result ...
    #   else
    #       ... do something with error ...
    #
    def get(self, path):
        response = self._request("GET", path)
        return self._handle_response(response)

    #
    # Performs a POST request to the Speakap API
    #
    # @param path The path of the REST endpoint, including optional query parameters.
    # @param data Object representing the JSON object to submit.
    #
    # @return A tuple containing the parsed JSON reply (in case of success) and an error object
    #         (in case of an error).
    #
    # Note that if you want to make a POST request to an action (generally all REST endpoints
    # without trailing slash), you should use the post_action() method instead, as this will use
    # the proper formatting for the POST data.
    #
    # Example:
    #
    #   (json_result, error) = speakap_api.post("/networks/%s/messages/" % network_eid, {
    #       "body": "test 123",
    #       "messageType": "update",
    #       "recipient": { "type": "network", "EID": network_eid }
    #   })
    #   if json_result:
    #       ... do something with json_result ...
    #   else
    #       ... do something with error ...
    #
    def post(self, path, data):
        response = self._request("POST", path, json.dumps(data))
        return self._handle_response(response)

    #
    # Performs a POST request to an action endpoint in the Speakap API
    #
    # @param path The path of the REST endpoint, including optional query parameters.
    # @param data Optional object containing the form parameters to submit.
    #
    # @return A tuple containing the parsed JSON reply (in case of success) and an error object
    #         (in case of an error).
    #
    # Example:
    #
    #   (json_result, error) = speakap_api.post_action("/networks/%s/messages/%s/markread" % (network_eid, message_eid))
    #   if json_result:
    #       ... do something with json_result ...
    #   else
    #       ... do something with error ...
    #
    def post_action(self, path, data=None):
        response = self._request("POST", path, urllib.urlencode(data) if data else None)
        return self._handle_response(response)

    #
    # Performs a PUT request to the Speakap API
    #
    # @param path The path of the REST endpoint, including optional query parameters.
    # @param data Object representing the JSON object to submit.
    #
    # @return A tuple containing the parsed JSON reply (in case of success) and an error object
    #         (in case of an error).
    #
    # Example:
    #
    #   (json_result, error) = speakap_api.get("/networks/%s/timeline/?embed=messages.author" % network_eid)
    #   if json_result:
    #       ... do something with json_result ...
    #   else
    #       ... do something with error ...
    #
    def put(self, path, data):
        response = self._create_connection("PUT", path, json.dumps(data))
        return self._handle_response(response)

    #
    # Validates a the signature of a signed request
    #
    # @param params Object containing POST parameters passed during the signed request
    #
    # @return True or False depending on whether the signature matches the parameters.
    #
    def validate_signature(self, params):
        signature = params["signature"]

        keys = params.keys()
        keys.sort()
        query_string = "&".join(quote(key, "~") + "=" + quote(params[key], "~") \
                       for key in keys if key != "signature")
        encoded_payload = base64.b64encode(query_string)
        computed_hash = base64.b64encode(hmac.new(self.app_secret, encoded_payload, hashlib.sha256)
                                             .hexdigest())

        return computed_hash == signature

    def _request(self, method, path, data=None):
        separator = "&" if "?" in path else "?"
        path += "%saccess_token=%s" % (separator, self.access_token)

        if urlfetch:
            response = urlfetch.fetch("https://" + SPEAKAP_API_HOST + path,
                                      method=method,
                                      payload=data,
                                      validate_certificate=True)
            status = response.status_code
            data = response.content
        else:
            connection = httplib.HTTPSConnection(SPEAKAP_API_HOST)
            connection.request(method, path, data)
            response = connection.getresponse()
            status = response.status
            data = response.read()
            connection.close()

        return (status, data)

    def _handle_response(self, response):
        (status, data) = response

        try:
            json_result = json.loads(data)
        except:
            status = 400
            json_result = { "code": -1001, "message": "Unexpected Reply" }

        if status >= 200 and status < 300:
            return (json_result, None)
        else:
            return (None, { "code": json_result["code"], "message": json_result["message"] })
