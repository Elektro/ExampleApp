/*!
 * Speakap API integration for 3rd party apps
 * http://www.speakap.nl/
 *
 * Copyright (C) 2013 Speakap BV
 */
(function(factory) {
    if (typeof define === "function" && define.amd) {
        // AMD. Register as anonymous module.
        define(["jquery"], factory);
    } else {
        // Browser globals.
        window.Speakap = factory(jQuery);
    }
}(function($) {

    "use strict";

    /**
     * The global Speakap object.
     *
     * This object is either imported through the AMD module loader or is accessible as a global
     * Speakap variable. It inherits the appId and consumerSecret properties that were already
     * present in the global window scope.
     */
    var Speakap = {};

    /**
     * App ID. This UD is expected to be set on the global Speakap object before this library is
     * loaded.
     */
    Speakap.appId = window.Speakap.appId || "APP ID NOT SET";

    /**
     * Consumer secret used for authenticating the app. This secret is expected to be set on the
     * global Speakap object before this library is loaded.
     */
    Speakap.consumerSecret = window.Speakap.consumerSecret || "CONSUMER SECRET NOT SET";

    /**
     * Version of the Speakap API integration library.
     */
    Speakap.version = "0.1";

    Speakap.API = {

        /**
         * Sends a remote request to the API.
         *
         * This method can be used as a drop-in replacement for $.ajax(), but there are a few
         * conveniences as well as catches:
         * - All requests are automatically signed using the access token of the host application,
         *   but the App ID is sent along, possibly limiting the scope to which the app has access.
         * - Error handlers will receive an error object (with code and message properties) as their
         *   first argument, instead of a jqXHR object.
         * - The only supported HTTP method is GET.
         */
        ajax: function(url, settings) {

            if (settings) {
                settings.url = url;
            } else if (typeof url === "string") {
                settings = { url: url };
            } else {
                settings = url;
            }

            settings.type = "GET";

            var context = settings.context;

            var successCallback = settings.success;
            delete settings.success;

            var errorCallback = settings.error;
            delete settings.error;

            return call("ajax", settings, { expectResult: true }).then(function() {
                if (successCallback) {
                    successCallback.apply(context, arguments);
                }
            }, function() {
                if (errorCallback) {
                    errorCallback.apply(context, arguments);
                }
            });
        }

    };

    /**
     * Retrieves the currently logged in user.
     *
     * This method returns a $.Deferred object that is resolved with the user object as first
     * argument when successful.
     *
     * @param options Optional options object. May contain a context property containing the context
     *                in which the deferred listeners will be executed.
     */
    Speakap.getUser = function(options) {

        options = options || {};

        return call("getUser", null, { context: options.context, expectResult: true });
    };

    // PRIVATE methods

    var callId = 0;
    var calls = {};

    function call(method, data, options) {

        data = data || {};

        options = options || {};

        var deferred = new $.Deferred();

        if (options.expectResult) {
            callId++;
            calls[callId] = {
                context: options.context,
                deferred: deferred
            };
        } else {
            deferred.resolveWith(options.context);
        }

        window.parent.postMessage({
            appId: Speakap.appId,
            callId: callId,
            consumerSecret: Speakap.consumerSecret,
            method: method,
            settings: data
        }, "*");

        return deferred.promise();
    }

    function handleMessage(event) {

        var data = event.data || {};

        if (calls.hasOwnProperty(data.callId)) {
            var callback = calls[callId];
            var deferred = callback.deferred;
            if (data.error.code === 0) {
                deferred.resolveWith(callback.context, [data.result]);
            } else {
                deferred.rejectWith(callback.context, [data.error]);
            }
        }
    }

    function init() {

        window.addEventListener("message", handleMessage);
    }

    init();

    return Speakap;

}));
