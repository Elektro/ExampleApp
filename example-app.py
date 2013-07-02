import jinja2
import logging
import os
import webapp2

from google.appengine.ext import db


# this should be the App ID of your Speakap App. should be a valid EID
SPEAKAP_APP_ID = 'app01'

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])


class Product(db.Model):
    name = db.StringProperty(required=True)
    voters = db.StringListProperty(indexed=False)
    num_voters = db.IntegerProperty(default=0)


class MainPage(webapp2.RequestHandler):

    def get(self):
        # TODO: a real-world app would need to perform validation to ensure the user EID and
        #       and consumer secret really belong together, otherwise spoofing is as easy as
        #       replacing a request parameter
        consumer_secret = self.request.get('cs')
        user_eid = self.request.get('u')
        if consumer_secret and user_eid:
            self.showOverview(consumer_secret, user_eid)
        else:
            self.showAuthError()

    def post(self):
        consumer_secret = self.request.get('cs')
        user_eid = self.request.get('u')
        if consumer_secret and user_eid:
            product_name = self.request.get('productName')
            if product_name:
                q = Product.gql('WHERE name = :1', product_name)
                product = q.get()
                if product:
                    product.num_voters += 1
                else:
                    product = Product(name=product_name, num_voters=1)
                product.voters.append(user_eid)
                product.put()

        else:
            # TODO: the initial POST from Speakap needs to be signed and the signature needs
            #       to be verified here, otherwise any party can pretend to be Speakap and
            #       pretend to have authenticated the specified user
            # TODO: in addition to the following two parameters, you may also wish to check
            #       'networkEID' to separate the actual Speakap networks and use separate data sets
            #       for each
            consumer_secret = self.request.get('consumerSecret')
            user_eid = self.request.get('userEID')

        if consumer_secret and user_eid:
            self.showOverview(consumer_secret, user_eid)
        else:
            self.showAuthError()

    def showOverview(self, consumer_secret, user_eid):
        q = Product.gql('ORDER BY num_voters DESC')
        products = q.fetch(limit=20)

        template_values = {
            'appId': SPEAKAP_APP_ID,
            'consumerSecret': consumer_secret,
            'products': products,
            'userEID': user_eid
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

    def showAuthError(self):
        self.response.set_status(403)
        self.response.write('Forbidden - This App can only be accessed through Speakap')


def handle_404(request, response, exception):
    logging.exception(exception)
    response.write('Page Not Found')
    response.set_status(404)

def handle_500(request, response, exception):
    logging.exception(exception)
    response.write('Server Error')
    response.set_status(500)


application = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)
application.error_handlers[404] = handle_404
application.error_handlers[500] = handle_500
