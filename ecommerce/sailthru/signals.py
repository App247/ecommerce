import logging

from django.dispatch import receiver
from oscar.core.loading import get_class, get_model
import waffle

from ecommerce_worker.sailthru.v1.tasks import update_course_enrollment
from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.analytics.utils import silence_exceptions


logger = logging.getLogger(__name__)
post_checkout = get_class('checkout.signals', 'post_checkout')
basket_addition = get_class('basket.signals', 'basket_addition')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
SAILTHRU_CAMPAIGN = 'sailthru_bid'


@receiver(post_checkout)
@silence_exceptions("Failed to call Sailthru upon order completion.")
def process_checkout_complete(sender, order=None, user=None, request=None,  # pylint: disable=unused-argument
                              response=None, **kwargs):  # pylint: disable=unused-argument
    """Tell Sailthru when payment done.

    Arguments:
            Parameters described at http://django-oscar.readthedocs.io/en/releases-1.1/ref/signals.html
    """

    if not waffle.switch_is_active('sailthru_enable'):
        return

    partner = order.site.siteconfiguration.partner
    if not partner.enable_sailthru:
        return

    # get campaign id from cookies, or saved value in basket
    message_id = None
    if request:
        message_id = request.COOKIES.get('sailthru_bid')

    if not message_id:
        saved_id = BasketAttribute.objects.filter(
            basket=order.basket,
            attribute_type=_get_attribute_type()
        )
        if len(saved_id) > 0:
            message_id = saved_id[0].value_text

    # loop through lines in order
    #  If multi product orders become common it may be worthwhile to pass an array of
    #  orders to the worker in one call to save overhead, however, that would be difficult
    #  because of the fact that there are different templates for free enroll versus paid enroll
    for line in order.lines.all():

        # get product
        product = line.product

        # ignore everything except course seats.  no support for coupons as of yet
        product_class_name = product.get_product_class().name
        if product_class_name == SEAT_PRODUCT_CLASS_NAME:

            price = line.line_price_excl_tax

            course_id = product.course_id

            # pass event to ecommerce_worker.sailthru.v1.tasks to handle asynchronously
            update_course_enrollment.delay(order.user.email, _build_course_url(course_id),
                                           False, mode_for_seat(product),
                                           unit_cost=price, course_id=course_id, currency=order.currency,
                                           site_code=partner.short_code,
                                           message_id=message_id)


@receiver(basket_addition)
@silence_exceptions("Failed to call Sailthru upon basket addition.")
def process_basket_addition(sender, product=None, user=None, request=None, basket=None,
                            **kwargs):  # pylint: disable=unused-argument
    """Tell Sailthru when payment started.

    Arguments:
            Parameters described at http://django-oscar.readthedocs.io/en/releases-1.1/ref/signals.html
    """

    if not waffle.switch_is_active('sailthru_enable'):
        return

    partner = request.site.siteconfiguration.partner
    if not partner.enable_sailthru:
        return

    # ignore everything except course seats.  no support for coupons as of yet
    product_class_name = product.get_product_class().name
    if product_class_name == SEAT_PRODUCT_CLASS_NAME:

        course_id = product.course_id

        stock_record = product.stockrecords.first()
        if stock_record:
            price = stock_record.price_excl_tax
            currency = stock_record.price_currency

        # return if no price, no need to add free items to shopping cart
        if not price:
            return

        # save Sailthru campaign ID, if there is one
        message_id = request.COOKIES.get('sailthru_bid')
        if message_id and basket:
            BasketAttribute.objects.update_or_create(
                basket=basket,
                attribute_type=_get_attribute_type(),
                value_text=message_id
            )

        # pass event to ecommerce_worker.sailthru.v1.tasks to handle asynchronously
        update_course_enrollment.delay(user.email, _build_course_url(course_id), True, mode_for_seat(product),
                                       unit_cost=price, course_id=course_id, currency=currency,
                                       site_code=partner.short_code,
                                       message_id=message_id)


def _build_course_url(course_id):
    """Build a course url from a course id and the host"""
    return get_lms_url('courses/{}/info'.format(course_id))


def _get_attribute_type():
    """ Read attribute type for Sailthru campaign id"""
    try:
        attribute_type = BasketAttributeType.objects.get(name=SAILTHRU_CAMPAIGN)
    except BasketAttributeType.DoesNotExist:
        attribute_type = BasketAttributeType.objects.create(name=SAILTHRU_CAMPAIGN)
    return attribute_type