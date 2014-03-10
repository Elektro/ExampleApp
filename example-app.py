import jinja2
import logging
import os
import speakap
import webapp2

from google.appengine.ext import db

from speakap_api import speakap_api
from speakap_api import SPEAKAP_APP_ID

from urllib import quote

from webapp2_extras import sessions


config = {}
config["webapp2_extras.sessions"] = {
    "secret_key": "fi3vjhugu3uk,hlncwicew8023p;23dgvxgthg",
}

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=["jinja2.ext.autoescape"])


class Product(db.Model):
    name = db.StringProperty(required=True)
    voters = db.StringListProperty(indexed=False)
    num_voters = db.IntegerProperty(default=0)


class MainPage(webapp2.RequestHandler):

    def dispatch(self):
        # by default, the session ID is set in the Cookie header, but we can't rely on
        # cookies because of 3rd party cookie restrictions. so we pass the session ID through GET
        # parameters and unset the cookie before the response is sent
        self.session_id = self.request.get("SESSION")
        if self.session_id:
            self.request.cookies["session"] = self.session_id
            self.session_store = sessions.get_store(request=self.request)
            self.session # touch the object to guarantee its instantiation
        else:
            self.session_store = sessions.get_store(request=self.request)

            try:
                # there was no session yet, so we assume a valid signed request from Speakap
                # if the signed request is not valid, an exception is raised
                signed_params = dict(self.request.params)
                speakap_api.validate_signature(signed_params)

                # we copy all parameters from the signed request to a new user session (the session
                # is created implicitly), so the params are available on follow-up requests
                for key in signed_params:
                    self.session[key] = signed_params[key]

                self.session_store.save_sessions(self.response)
                # ugly method to get the session ID from the Set-Cookie header
                self.session_id = self.response.headers["Set-Cookie"].split(";")[0].split("=", 2)[1]
            except speakap.SignatureValidationError, exception:
                print exception
                self.show_auth_error()
                return

        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)
            try:
                self.response.unset_cookie("session")
            except:
                pass

    def get(self):
        try:
            self.verify_session()

            self.show_overview()
        except Exception, exception:
            self.show_auth_error()

    def post(self):
        try:
            self.verify_session()

            # add our vote for a product, if requested
            product_name = self.request.get("productName")
            if product_name:
                q = Product.gql("WHERE name = :1", product_name)
                product = q.get()
                if not product:
                    product = Product(name=product_name, num_voters=0)
                user_eid = self.session.get("userEID")
                if user_eid not in product.voters:
                    product.voters.append(user_eid)
                    product.num_voters += 1
                product.put()

            self.show_overview()
        except Exception, exception:
            print exception
            self.show_auth_error()

    @webapp2.cached_property
    def session(self):
        return self.session_store.get_session(backend="memcache")

    def show_auth_error(self):
        """Displays an error message."""
        self.response.set_status(403)
        self.response.write("Forbidden - This App can only be accessed through Speakap")

    def show_overview(self):
        """Display the default overview."""
        q = Product.gql("ORDER BY num_voters DESC")
        products = q.fetch(limit=20)

        # because the App Engine DB uses eventual consistency, we may have to fake the result
        # if we just voted on something by manually adding our own vote if it doesn't exist yet
        product_name = self.request.get("productName")
        user_eid = self.session.get("userEID")
        if product_name:
            found = False
            for product in products:
                if product.name == product_name:
                    if user_eid not in product.voters:
                        product.voters.append(user_eid)
                    found = True
            if not found and len(products) < 20:
                product = Product(name=product_name, num_voters=1)
                product.voters.append(user_eid)
                products.append(product)

        template_values = {
            "app_id": SPEAKAP_APP_ID,
            "products": products,
            "session_id": self.session_id,
            "signed_request": speakap.signed_request(self.session),
            "user_eid": user_eid
        }

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render(template_values))

    def verify_session(self):
        if not self.session_id:
            raise Exception("No session ID available")

        self.request.headers["Cookie"] = "session=" + quote(self.session_id)
        if not self.session.get("userEID"):
            raise Exception("No valid session")


def handle_404(request, response, exception):
    logging.exception(exception)
    response.write("Page Not Found")
    response.set_status(404)

def handle_500(request, response, exception):
    logging.exception(exception)
    response.write("Server Error")
    response.set_status(500)


application = webapp2.WSGIApplication([
    ("/", MainPage),
], config=config, debug=True)
application.error_handlers[404] = handle_404
application.error_handlers[500] = handle_500
