import jinja2
import logging
import os
import speakap
import webapp2

from google.appengine.ext import db
from speakap_api import speakap_api
from speakap_api import SPEAKAP_APP_ID


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=["jinja2.ext.autoescape"])


class Product(db.Model):
    name = db.StringProperty(required=True)
    voters = db.StringListProperty(indexed=False)
    num_voters = db.IntegerProperty(default=0)


class MainPage(webapp2.RequestHandler):

    def get(self):
        self.signed_params = dict(self.request.params)

        if speakap_api.validate_signature(self.signed_params):
            self.show_overview()
        else:
            self.show_auth_error()

    def post(self):
        self.signed_params = dict(self.request.params)

        product_name = self.request.get("productName")
        if product_name:
            del self.signed_params["productName"]

        if speakap_api.validate_signature(self.signed_params):
            if product_name:
                q = Product.gql("WHERE name = :1", product_name)
                product = q.get()
                if product:
                    product.num_voters += 1
                else:
                    product = Product(name=product_name, num_voters=1)
                product.voters.append(self.request.get("userEID"))
                product.put()

            self.show_overview()
        else:
            self.show_auth_error()

    def show_overview(self):
        q = Product.gql("ORDER BY num_voters DESC")
        products = q.fetch(limit=20)

        template_values = {
            "app_id": SPEAKAP_APP_ID,
            "products": products,
            "signed_request": speakap.signed_request(self.signed_params),
            "user_eid": self.request.get("userEID")
        }

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render(template_values))

    def show_auth_error(self):
        self.response.set_status(403)
        self.response.write("Forbidden - This App can only be accessed through Speakap")


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
], debug=True)
application.error_handlers[404] = handle_404
application.error_handlers[500] = handle_500
