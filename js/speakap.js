/*!
 * Speakap API integration for 3rd party apps, version 1.0
 * http://www.speakap.nl/
 *
 * Copyright (C) 2013-2014 Speakap BV
 */
(function(factory) {

    "use strict";

    if (typeof define === "function" && define.amd) {
        // AMD. Register as anonymous module.
        define(["jquery"], factory);
    } else {
        // Browser globals.
        /* global jQuery */
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
        this.signedRequest = window.Speakap.signedRequest || "";

        /**
         * Token to use to identify the consumer with the API proxy.
         *
         * Will be set by the handshake procedure. Be sure not to call any other methods before the
         * handshake has completed by using the doHandshake promise.
         *
         * If this file is loaded in the context of a lightbox, the token is injected automatically.
         */
        this.token = window.Speakap.token || "";

        window.addEventListener("message", $.proxy(this._handleMessage, this));

        this._callId = 0;
        this._calls = {};

        this._listeners = {};

        if (this.signedRequest) {
            this._doHandshake();
        }
    };

    /**
     * Sends a remote request to the API.
     *
     * This method can be used as a replacement for $.ajax(), but with a few differences:
     * - All requests are automatically signed using the access token of the host application,
     *   but the app's permissions may be limited based on the App ID.
     * - Error handlers will receive an error object (with code and message properties) as their
     *   first argument, instead of a jqXHR object.
     * - The URL property is interpreted as a path under the Speakap API, limited in scope to
     *   the current network. Eg. use "/users/" to request
     *                                    "https://api.speakap.nl/networks/:networkEID/users/".
     * - The only supported HTTP method is GET.
     */
    Speakap.prototype.ajax = function(url, settings) {

        if (settings) {
            settings.url = url;
        } else if (typeof url === "string") {
            settings = { url: url };
        } else {
            settings = url;
        }

        settings.type = "GET";

        var context = settings.context;
        delete settings.context;

        var successCallback = settings.success;
        delete settings.success;

        var errorCallback = settings.error;
        delete settings.error;

        var promise = this._call("ajax", settings, { context: context, expectResult: true });

        if (successCallback) {
            promise.done(function() {
                successCallback.apply(context, arguments);
            });
        }
        if (errorCallback) {
            promise.fail(function() {
                errorCallback.apply(context, arguments);
            });
        }

        return promise;
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

    /**
     * Stops listening to an event generated by the Speakap host application.
     *
     * @param event Event that was being listened to.
     * @param callback Callback function that was executed when the event was fired.
     * @param context Optional context in which the listener was executed.
     */
    Speakap.prototype.off = function(event, callback, context) {

        var listeners = this._listeners[event] || [];
        for (var i = 0; i < listeners.length; i++) {
            var listener = listeners[i];
            if (listener.callback === callback && listener.context === context) {
                listeners.splice(i, 1);
                i--;
            }
        }
        this._listeners[event] = listeners;
    };

    /**
     * Starts listening to an event generated by the Speakap host application.
     *
     * @param event Event to listen to.
     * @param listener Callback function to execute when the event is fired.
     * @param context Optional context in which to execute the listener.
     */
    Speakap.prototype.on = function(event, callback, context) {

        var listeners = this._listeners[event] || [];
        listeners.push({ callback: callback, context: context });
        this._listeners[event] = listeners;
    };

    /**
     * Presents a lightbox to the user.
     *
     * For security reasons, the lightbox presented contains a sandboxed iframe whose content is
     * defined by the parameters given here.
     *
     * By default, this iframe has no permissions to execute scripts of any kind. Permissions to
     * execute scripts are granted if events handlers or JavaScript URLs are specified or when the
     * hasScript property is explicitly set to true. An important caveat is that when JavaScript
     * permissions are granted, the lightbox will *not* work in Internet Explorer.
     *
     * @param options Required options object. May contain the following properties:
     *                buttons - Array of button objects for the buttons to show below the lightbox.
     *                          Each button object may have the following properties:
     *                          enabled - Boolean indicating whether the button is enabled. Default
     *                                    is true.
     *                          label - String label of the button.
     *                          positioning - String "left" or "right", depending on which side the
     *                                        button should be displayed. Default is "right".
     *                          primary - Boolean indicating whether the button is the primary
     *                                    button. The primary button is styled in the call-to-action
     *                                    color (typically green) and is selected when the user
     *                                    presses Ctrl+Enter.
     *                          type - String type of the button, used for identifying the button.
     *                                 The following types are predefined:
     *                                 "close" - Closes the lightbox when clicked.
     *                                 "resolve" - Resolves the lightbox when clicked.
     *                                 You can listen to other buttons by listening to the
     *                                 "click button[data-type='<type>']" event.
     *                content - HTML content to display in the body of the iframe.
     *                context - Context in which to execute the promise callbacks.
     *                css - Array of URLs to CSS resources that should be included by the iframe.
     *                      Note that Speakap's "base.css" and "branding.css" are always included
     *                      and don't need to be specified in this array.
     *                events - Map of event handlers to be active on the given HTML content. The
     *                         map follows the same format as used by Backbone's delegateEvents()
     *                         method: http://backbonejs.org/#View-delegateEvents
     *                         Note that these event handlers execute within the context of the
     *                         iframe and thus cannot access any variables from their outer scope.
     *                         Nor will you have access to jQuery methods or other libraries unless
     *                         you include it yourself as JavaScript resource.
     *                         Finally, the "submit" event can be caught (and cancelled, by
     *                         returning false from the event handler) to perform any validation or
     *                         other processing when the lightbox is resolved.
     *                hasScripts - This option has to be set to true to enable the execution of
     *                             scripts in the lightbox. It is implicitly set to true if any
     *                             events or JavaScript URLs are specified, but has to be explicitly
     *                             set to true if you specify inline event handlers in your HTML
     *                             content, for example. An important caveat is that when this
     *                             property is true (whether implicit or explicit) the lightbox
     *                             will *not* work in Internet Explorer.
     *                js - Array of URLs to JavaScript resources that should be loaded by the
     *                     iframe. Note that you need to include your own reference to this
     *                     speakap.js file if you want to be able to use this API from the iframe.
     *                height - Lightbox height in pixels. The minimum permitted height is 100
     *                         pixels, and the maximum permitted height is 540 pixels.
     *                title - Title of the lightbox.
     *                width - Lightbox width in pixels. The minimum permitted width is 100
     *                        pixels, and the maximum permitted width is 740 pixels.
     *
     * @return jQuery Deferred promise that gets fulfilled when the lightbox is resolved, or failed
     *         when the lightbox is closed otherwise.
     *
     * When the lightbox is resolved, the promise callback receives a data parameter that resembles
     * a form submit like those sent with an HTTP POST request. The data object consists of
     * key-value pairs with each key being the name of an input element displayed in the lightbox,
     * and the value being the input element's value.
     *
     * All URLs given for CSS and JavaScript resources have to be absolute URLs.
     *
     * Within the iframe, this speakap.js file is available if you include it with the JavaScript
     * resources, giving you access to the global Speakap object from the iframe (including event
     * handlers defined on the lightbox). Specifically, the following methods can be used from a
     * lightbox context:
     * - getLoggedInUser()
     * - setButtonEnabled()
     * - showError()
     */
    Speakap.prototype.openLightbox = function(options) {

        var data = {};
        for (var key in options) {
            if (options.hasOwnProperty(key) && key !== "context") {
                var value;
                if (key === "events") {
                    value = {};
                    var events = options[key];
                    for (var eventName in events) {
                        if (events.hasOwnProperty(eventName)) {
                            value[eventName] = events[eventName].toString();
                        }
                    }
                } else {
                    value = options[key];
                }

                data[key] = value;
            }
        }

        if (data.events || data.js) {
            data.hasScripts = true;
        }

        return this._call("openLightbox", data, {
            context: options.context,
            expectResult: true
        });
    };

    /**
     * Sends a reply to an event generated by the Speakap host application.
     *
     * @param event Event to reply to.
     * @param data Data to send back to the host application.
     */
    Speakap.prototype.replyEvent = function(event, data) {

        if (event.eventId) {
            this._call("replyEvent", $.extend(data, { eventId: event.eventId }));
        } else {
            console.log("The host did not expect a reply to this event");
        }
    };

    /**
     * Toggles the enabled state of one of the lightbox's buttons.
     *
     * @param type Type of the button to enable or disable.
     * @param enabled True if the button should be enabled, false if it should be disabled.
     *
     * This method is only available from the content of a lightbox iframe.
     */
    Speakap.prototype.setButtonEnabled = function(type, enabled) {

        return this._call("setButtonEnabled", { type: type, enabled: enabled });
    };

    /**
     * Shows an error message to the user.
     *
     * @param message Localized message to show the user.
     */
    Speakap.prototype.showError = function(message) {

        return this._call("showError", { message: message });
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

        if (data.event) {
            var listeners = this._listeners[data.event] || [];
            for (var i = 0; i < listeners.length; i++) {
                var listener = listeners[i];
                listener.callback.call(listener.context, data.data);
            }
        } else {
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
        }
    };

    return new Speakap();

}));
