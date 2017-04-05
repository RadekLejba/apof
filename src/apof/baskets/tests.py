from decimal import Decimal

from django.contrib.admin import ModelAdmin
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.admin.filters import SimpleListFilter, ListFilter
from django.contrib.auth.models import Permission, User

from django.contrib.admin.options import ModelAdmin, BaseModelAdmin
from django.contrib.admin.filters import SimpleListFilter, ListFilter
from django.core.files import File
from django.shortcuts import reverse
from django.test import TestCase
from mock import MagicMock, patch

from baskets.admin import RestaurantListFilter, OrderAdmin, BasketAdmin
from baskets.models import Basket, Order
from baskets.templatetags.get_item import get_item
from baskets.views import OrderDeleteView, OrderListView
from menus.models import (
    Ingredient,
    Meal,
    Menu,
    Price,
    Size,
    Topping
)
from restaurants.models import Restaurant


class BasketTestCase(TestCase):
    fixtures = ['test_user_data.json']

    def test_string_representation(self):
        basket = Basket(owner=User.objects.get(username='christopher'))
        self.assertEqual(str(basket), 'Basket christopher')


class OrderTestMixin:

    @patch('django.core.files.storage.default_storage._wrapped')
    def setUp(self, mocked_storage):
        file_mock = MagicMock(spec=File, name='FileMock')
        file_mock.name = 'test1.jpg'
        restaurant = Restaurant.objects.create(name='test restaurant2', logo=file_mock)
        menu = Menu.objects.create(restaurant=restaurant)
        size = Size.objects.create(menu=menu, value=15, value_unit='cm')
        test_meal = Meal.objects.create(menu=menu, name='test_meal')
        test1_topping = Topping.objects.create(
            menu=menu,
            ingredient=Ingredient.objects.create(
                name='test1_ingredient'
            )
        )
        test2_topping = Topping.objects.create(
            menu=menu,
            ingredient=Ingredient.objects.create(
                name='test2_ingredient'
            )
        )
        Price.objects.bulk_create([
            Price(value=22.99, size=size, content_object=test_meal),
            Price(value=2.5, size=size, content_object=test1_topping),
            Price(value=1.25, size=size, content_object=test2_topping)
        ])
        self.order = Order.objects.create(
            basket=Basket.objects.create(owner=User.objects.get(username='christopher')),
            meal=test_meal,
            size=size
        )
        self.order.toppings.set([test1_topping, test2_topping])
        self.data_mock = MagicMock()
        self.test_order = OrderAdmin(self.data_mock, self.data_mock)


class OrderTestCase(OrderTestMixin, TestCase):
    fixtures = ['test_user_data.json']

    def test_string_representation(self):
        basket = Basket(owner=User.objects.get(username='christopher'))
        meal = Meal(menu=Menu(restaurant=Restaurant(name='restaurant')), name='soup')

        order = Order(basket=basket, meal=meal)
        self.assertEqual(str(order), 'christopher soup')


    def test_get_restaurant(self):
        self.assertEqual(self.order.get_restaurant_name(), 'test restaurant2')

    def test_get_total_price(self):
        expected_total_price = Decimal('26.74')
        self.assertEqual(self.order.get_total_price(), expected_total_price)


class OrderListViewTestCase(OrderTestMixin, TestCase):
    fixtures = ['test_user_data.json']

    def test_constants(self):
        self.assertEqual(OrderListView.model, Order)
        self.assertEqual(OrderListView.permission_required, ('baskets.delete_order', ))
        self.assertTrue(OrderListView.raise_exception)
        self.assertEqual(OrderListView.ordering, ('meal__menu__restaurant', ))

    def test_anonymous_user_gets_403(self):
        response = self.client.get(reverse('order-list'))
        self.assertEqual(response.status_code, 403)

    def test_logged_user_without_permission_gets_403(self):
        self.client.force_login(User.objects.get(username='christopher'))

        response = self.client.get(reverse('order-list'))
        self.assertEqual(response.status_code, 403)

    def test_logged_user_with_permission(self):
        user = User.objects.get(username='christopher')
        user.user_permissions.add(Permission.objects.get(codename='delete_order'))
        self.client.force_login(user)

        response = self.client.get(reverse('order-list'))
        self.assertEqual(response.status_code, 200)


class OrderDeleteViewTestCase(OrderTestMixin, TestCase):
    fixtures = ['test_user_data.json']

    def test_constants(self):
        self.assertEqual(OrderDeleteView.model, Order)
        self.assertEqual(OrderDeleteView.permission_required, ('baskets.delete_order', ))
        self.assertTrue(OrderDeleteView.raise_exception)

    def test_anonymous_user_gets_403(self):
        response = self.client.get(reverse('order-delete', kwargs={'pk': self.order.pk}))
        self.assertEqual(response.status_code, 403)

    def test_logged_user_without_permission_gets_403(self):
        self.client.force_login(User.objects.get(username='christopher'))

        response = self.client.get(reverse('order-delete', kwargs={'pk': self.order.pk}))
        self.assertEqual(response.status_code, 403)

    def test_logger_user_with_permission(self):
        user = User.objects.get(username='christopher')
        user.user_permissions.add(Permission.objects.get(codename='delete_order'))
        self.client.force_login(user)

        response = self.client.get(reverse('order-delete', kwargs={'pk': self.order.pk}))
        self.assertEqual(response.status_code, 200)


class GetItemTagTestCase(TestCase):
    def test_get_item(self):
        test_dict = {
            'a': 1,
            '2': 'b'
        }
        self.assertEqual(get_item(test_dict, 'a'), 1)
        self.assertIsNone(get_item(test_dict, 'b'))


class AddToBasketViewTestCase(TestCase):
    fixtures = ['test_user_data.json']

    @patch('django.core.files.storage.default_storage._wrapped')
    def setUp(self, mocked_storage):
        self.user = User.objects.get(username='christopher')
        file_mock = MagicMock(spec=File, name='FileMock')
        file_mock.name = 'test1.jpg'
        restaurant = Restaurant.objects.create(name='test restaurant2', logo=file_mock)
        menu = Menu.objects.create(restaurant=restaurant)
        self.size = Size.objects.create(menu=menu, value=15, value_unit='cm')
        self.meal = Meal.objects.create(menu=menu, name='test_meal')
        self.price = Price.objects.create(value=22.99, size=self.size, content_object=self.meal)

    def _get_url(self, meal, price):
        url = reverse(
            'add-meal-to-basket',
            kwargs={
                'meal_id': meal.id,
                'meal_price_id': price.id
            }
        )
        return url

    def test_anonymous_user_is_redirected_to_login_view(self):
        response = self.client.get(self._get_url(self.meal, self.price))
        self.assertRedirects(
            response,
            '{}{}{}'.format(
                reverse('login'),
                '?next=',
                self._get_url(self.meal, self.price)
            )
        )

    def test_logged_user_can_create_order_with_meal_in_basket(self):
        self.client.force_login(self.user)

        response = self.client.get(self._get_url(self.meal, self.price))
        order = Order.objects.get(pk=1)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.all().count(), 1)
        self.assertEqual(order.basket.owner, self.user)
        self.assertEqual(order.meal, self.meal)
        self.assertEqual(order.size, self.size)

    def test_logged_user_is_redirected_after_creating_order(self):
        self.client.force_login(self.user)
        expected_url = reverse('meal-list', kwargs={'restaurant_pk': 1})

        response = self.client.get(
            self._get_url(
                self.meal,
                self.price
            ),
            HTTP_REFERER=expected_url
        )
        self.assertRedirects(response, expected_url)


class AdminTestCase(OrderTestMixin, TestCase):
    fixtures = ['test_user_data.json']

    def test_admin_restaurant_list(self):
        testFilter = RestaurantListFilter(
            self.data_mock,
            self.data_mock,
            self.data_mock,
            self.data_mock
        )
        data1 = testFilter.lookups(self.data_mock, self.data_mock)
        data2 = testFilter.queryset(self.data_mock, data1)
        self.assertEqual(data1[0][1], 'test restaurant2')
        self.assertEqual(data2[0][1], 'test restaurant2')

    def test_admin_get_meal_name(self):
        data = self.test_order.get_meal_name(self.order)
        self.assertEqual(data, 'test_meal')

    def test_admin_get_order_price(self):
        data = self.test_order.get_order_price(self.order)
        self.assertEqual(data, Decimal('26.74'))

    def test_admin_get_order_restaurant_name(self):
        data = self.test_order.get_order_restaurant_name(self.order)
        self.assertEqual(data, 'test restaurant2')

    def test_admin_get_toppings(self):
        data = self.test_order.get_toppings(self.order)
        self.assertEqual(data, 'test1_ingredient, test2_ingredient')

    def test_OrderAdmin_mro(self):
        orderMRO = OrderAdmin.__mro__
        expectedMRO = (OrderAdmin, ModelAdmin, BaseModelAdmin, object)
        self.assertEqual(orderMRO, expectedMRO)

    def test_BasketAdmin_mro(self):
        basketMRO = BasketAdmin.__mro__
        expectedMRO = (BasketAdmin, ModelAdmin, BaseModelAdmin, object)
        self.assertEqual(basketMRO, expectedMRO)

    def test_RestaurantListFilter_mro(self):
        filterMRO = RestaurantListFilter.__mro__
        expectedMRO = (RestaurantListFilter, SimpleListFilter, ListFilter, object)
        self.assertEqual(filterMRO, expectedMRO)
