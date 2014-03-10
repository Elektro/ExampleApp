# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import httplib
import iso8601
import json
import logging

from datetime import datetime;
from datetime import timedelta;

try:
    from google.appengine.api import urlfetch
except ImportError:
    urlfetch = None

from urllib import quote


SIGNATURE_WINDOW_SIZE = 1; # minute


class SignatureValidationError(Exception):
    """
    Exception thrown when a signed request is invalid.
    """
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


def signed_request(params):
    """
    Generates the signed request string from the parameters.

    @param params Object containing POST parameters passed during the signed request.

    @return Query string containing the parameters of the signed request.

    Note this method does not calculate a signature; it simply generates the signed request from
    the parameters including the signature.
    """
    has_signature = False
    keys = params.keys()
    if "signature" in keys:
        has_signature = True
        keys.remove("signature")
    keys.sort()
    if has_signature:
        keys.append("signature")
    query_string = "&".join(quote(key, "~") + "=" + quote(params[key], "~") for key in keys)
    return query_string


class API:
    """
    Speakap API wrapper

    You should instantiate the Speakap API as follows:

      var Speakap = require("speakap");
      speakap_api = Speakap.API({
          "scheme": "https",
          "hostname": "api.speakap.io",
          "app_id": MY_APP_ID,
          "app_secret": MY_APP_SECRET
      })

      Obviously, MY_APP_ID and MY_APP_SECRET should be replaced with your actual App ID and secret
      (or be constants containing those).

      After you have instantiated the API wrapper, you can perform API calls as follows:

        (json_result, error) = speakap_api.get("/networks/%s/user/%s/" % (network_eid, user_eid))

        (json_result, error) = speakap_api.post("/networks/%s/messages/" % network_eid, {
            "body": "test 123",
            "messageType": "update",
            "recipient": { "type": "network", "EID": network_eid }
        })

      The JSON result contains the already parsed reply in case of success, but is None in case of
      an error. The error variable is None in case of success, but is an object containing code
      and message properties in case of an error.

      WARNING: If you use this class to make requests on any other platform than Google App Engine,
               the SSL certificate of the Speakap API service is not confirmed, leaving you
               vulnerable to man-in-the-middle attacks. This is due to a limitation of the SSL
               support in the Python framework. You are strongly advised to take your own
               precautions to make sure the certificate is valid.
    """
    def __init__(self, config):
        self.scheme = config["scheme"]
        self.hostname = config["hostname"]
        self.app_id = config["app_id"]
        self.app_secret = config["app_secret"]

        self.access_token = "%s_%s" % (self.app_id, self.app_secret)

    def delete(self, path):
        """
        Performs a DELETE request to the Speakap API

        @param path The path of the REST endpoint, including optional query parameters.

        @return A tuple containing the parsed JSON reply (in case of success) and an error object
                (in case of an error).

        Example:

          (json_result, error) = speakap_api.delete("/networks/%s/messages/%s/" % (network_eid, message_eid))
          if json_result:
              ... do something with json_result ...
          else
              ... do something with error ...
        """
        response = self._request("DELETE", path)
        return self._handle_response(response)

    def get(self, path):
        """
        Performs a GET request to the Speakap API

        @param path The path of the REST endpoint, including optional query parameters.

        @return A tuple containing the parsed JSON reply (in case of success) and an error object
                (in case of an error).

        Example:

          (json_result, error) = speakap_api.get("/networks/%s/timeline/?embed=messages.author" % network_eid)
          if json_result:
              ... do something with json_result ...
          else
              ... do something with error ...
        """
        response = self._request("GET", path)
        return self._handle_response(response)

    def post(self, path, data):
        """
        Performs a POST request to the Speakap API

        @param path The path of the REST endpoint, including optional query parameters.
        @param data Object representing the JSON object to submit.

        @return A tuple containing the parsed JSON reply (in case of success) and an error object
                (in case of an error).

        Note that if you want to make a POST request to an action (generally all REST endpoints
        without trailing slash), you should use the post_action() method instead, as this will use
        the proper formatting for the POST data.

        Example:

          (json_result, error) = speakap_api.post("/networks/%s/messages/" % network_eid, {
              "body": "test 123",
              "messageType": "update",
              "recipient": { "type": "network", "EID": network_eid }
          })
          if json_result:
              ... do something with json_result ...
          else
              ... do something with error ...
        """
        response = self._request("POST", path, json.dumps(data))
        return self._handle_response(response)

    def post_action(self, path, data=None):
        """
        Performs a POST request to an action endpoint in the Speakap API.

        @param path The path of the REST endpoint, including optional query parameters.
        @param data Optional object containing the form parameters to submit.

        @return A tuple containing the parsed JSON reply (in case of success) and an error object
                (in case of an error).

        Example:

          (json_result, error) = speakap_api.post_action("/networks/%s/messages/%s/markread" % (network_eid, message_eid))
          if json_result:
              ... do something with json_result ...
          else
              ... do something with error ...
        """
        response = self._request("POST", path, urllib.urlencode(data) if data else None)
        return self._handle_response(response)

    def put(self, path, data):
        """
        Performs a PUT request to the Speakap API.

        @param path The path of the REST endpoint, including optional query parameters.
        @param data Object representing the JSON object to submit.

        @return A tuple containing the parsed JSON reply (in case of success) and an error object
                (in case of an error).

        Example:

          (json_result, error) = speakap_api.get("/networks/%s/timeline/?embed=messages.author" % network_eid)
          if json_result:
              ... do something with json_result ...
          else
              ... do something with error ...
        """
        response = self._create_connection("PUT", path, json.dumps(data))
        return self._handle_response(response)

    def validate_signature(self, params):
        """
        Validates the signature of a signed request.

        @param params Object containing POST parameters passed during the signed request.

        Raises a SignatureValidationError if the signature doesn't match or the signed request is
        expired.
        """
        if "signature" not in params:
            raise SignatureValidationError("Parameters did not include a signature")

        signature = params["signature"]

        keys = params.keys()
        keys.sort()
        query_string = "&".join(quote(key, "~") + "=" + quote(params[key], "~") \
                       for key in keys if key != "signature")
        computed_hash = base64.b64encode(hmac.new(self.app_secret, query_string, hashlib.sha256)
                                             .hexdigest())

        if computed_hash != signature:
            raise SignatureValidationError("Invalid signature: " + query_string)

        issued_at = iso8601.parse_date(params["issuedAt"])
        expires_at = issued_at + timedelta(minutes=SIGNATURE_WINDOW_SIZE)
        if datetime.utcnow() > expires_at.replace(tzinfo=None):
            raise SignatureValidationError("Expired signature")

    def _request(self, method, path, data=None):
        headers = {"Authorization": "Bearer " + self.access_token}
        if urlfetch:
            response = urlfetch.fetch(self.scheme + "://" + self.hostname + path,
                                      headers=headers,
                                      method=method,
                                      payload=data,
                                      validate_certificate=True)
            status = response.status_code
            data = response.content
        else:
            if self.scheme == "https":
                connection = httplib.HTTPSConnection(self.hostname)
            else:
                connection = httplib.HTTPConnection(self.hostname)
            connection.request(method, path, data, headers)
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
