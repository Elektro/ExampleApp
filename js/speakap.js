/*!
 * Speakap API integration for 3rd party apps
 * http://www.speakap.nl/
 *
 * Copyright (C) 2013-2014 Speakap BV
 */
(function(factory) {
    if (typeof define === "function" && define.amd) {
        // AMD. Register as anonymous module.
        define(["jquery"], factory);
    } else {
        // Browser globals.
        window.Speakap = factory(jQuery);
    }
}(function($, undefined) {

    "use strict";

    /**
     * The global Speakap object.
     *
     * This object is either imported through the AMD module loader or is accessible as a global
     * Speakap variable.
     *
     * Before you load this library, you should set the App ID and the signed request that was
     * received by the application on the global Speakap object.
     *
     * Example:
     *
     *   <script type="text/javascript">
     *       var Speakap = { appId: "{{app_id|safe}}", signedRequest: "{{signed_request|safe}}" };
     *   </script>
     *   <script type="text/javascript" src="js/jquery.min.js"></script>
     *   <script type="text/javascript" src="js/speakap.js"></script>
     */
    var Speakap = function() {

        /**
         * The application's app ID.
         */
        this.appId = window.Speakap.appId || "APP ID IS MISSING";

        /**
         * Promise that will be fulfilled when the handshake has completed. You can use this to
         * make sure you don't run any code before the handshake has completed.
         *
         * Example:
         *
         *   Speakap.doHandshake.then(function() {
         *       // make calls to the Speakap API proxy...
         *   })
         */
        this.doHandshake = null;

        /**
         * The signed request posted to the application.
         */
        this.signedRequest = window.Speakap.signedRequest || "SIGNED REQUEST IS MISSING";

        /**
         * Token to use to identify the consumer with the API proxy.
         *
         * Will be set by the handshake procedure. Be sure not to call any other methods before the
         * handshake has completed.
         */
        this.token = "";

        window.addEventListener("message", $.proxy(this._handleMessage, this));

        this._callId = 0;
        this._calls = {};

        this._doHandshake();
    };

    /**
     * Retrieves the currently logged in user.
     *
     * This method returns a $.Deferred object that is resolved with the user object as first
     * argument when successful.
     *
     * The returned user object only contains the EID, name, fullName and avatarThumbnailUrl
     * properties.
     *
     * @param options Optional options object. May contain a context property containing the context
     *                in which the deferred listeners will be executed.
     */
    Speakap.prototype.getLoggedInUser = function(options) {

        options = options || {};

        return this._call("getLoggedInUser", null, {
            context: options.context,
            expectResult: true
        });
    };

    // PRIVATE methods

    Speakap.prototype._call = function(method, data, options) {

        options = options || {};

        var deferred = new $.Deferred();

        var cid;
        if (options.expectResult) {
            cid = "c" + this._callId++;
            this._calls[cid] = {
                context: options.context,
                deferred: deferred
            };
        } else {
            deferred.resolveWith(options.context);
        }

        window.parent.postMessage({
            appId: this.appId,
            callId: cid,
            method: method,
            settings: data || {},
            token: this.token
        }, "*");

        return deferred.promise();
    };

    Speakap.prototype._doHandshake = function() {

        this.doHandshake = this._call("handshake", { signedRequest: this.signedRequest }, {
            context: this,
            expectResult: true
        }).then(function(result) {
            this.token = result.token;
        });
    };

    Speakap.prototype._handleMessage = function(event) {

        var data = event.data || {};

        var calls = this._calls;
        if (calls.hasOwnProperty(data.callId)) {
            var callback = calls[data.callId];
            delete calls[data.callId];

            var deferred = callback.deferred;
            if (data.error.code === 0) {
                deferred.resolveWith(callback.context, [data.result]);
            } else {
                deferred.rejectWith(callback.context, [data.error]);
            }
        }
    };

    return new Speakap();

}));
