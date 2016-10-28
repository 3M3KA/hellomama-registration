try:
    import mock
except ImportError:
    from unittest import mock

from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from .metrics import MetricGenerator, send_metric
from .tests import AuthenticatedAPITestCase
from .models import Registration, Source


class MetricsGeneratorTests(AuthenticatedAPITestCase):
    def test_generate_metric(self):
        """
        The generate_metric function should call the correct function with the
        correct start and end datetimes.
        """
        generator = MetricGenerator()
        generator.foo_bar = mock.MagicMock()
        start = datetime(2016, 10, 26)
        end = datetime(2016, 10, 26)
        generator.generate_metric('foo.bar', start, end)

        generator.foo_bar.assert_called_once_with(start, end)

    def create_registration_on(self, timestamp, source, **kwargs):
        r = Registration.objects.create(
            mother_id='motherid', source=source, data=kwargs)
        r.created_at = timestamp
        r.save()
        return r

    def test_registrations_created_sum(self):
        """
        Should return the amount of registrations in the given timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(datetime(2016, 10, 14), source)  # Before
        self.create_registration_on(datetime(2016, 10, 15), source)  # On
        self.create_registration_on(datetime(2016, 10, 20), source)  # In
        self.create_registration_on(datetime(2016, 10, 25), source)  # On
        self.create_registration_on(datetime(2016, 10, 26), source)  # After

        reg_count = MetricGenerator().registrations_created_sum(start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_created_total_last(self):
        """
        Should return the total amount of registrations at the 'end' point in
        time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(datetime(2016, 10, 14), source)  # Before
        self.create_registration_on(datetime(2016, 10, 25), source)  # On
        self.create_registration_on(datetime(2016, 10, 26), source)  # After

        reg_count = MetricGenerator().registrations_created_total_last(
            start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_unique_operators_sum(self):
        """
        Should return the amount of new operators in the given timeframe.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        # Registration before should exclude 1
        self.create_registration_on(
            datetime(2016, 10, 14), source, operator_id='1')
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='1')
        # Two registrations during should exclude 2
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='2')
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='2')
        # Registration after shouldn't exclude 3
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='3')
        self.create_registration_on(
            datetime(2016, 10, 26), source, operator_id='3')

        reg_count = MetricGenerator().registrations_unique_operators_sum(
            start, end)
        self.assertEqual(reg_count, 1)

    def test_registrations_msg_type_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific message type.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_type='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, msg_type='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_type='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_type='type1')  # After

        reg_count = MetricGenerator().registrations_msg_type_sum(
            'type1', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_msg_type_sum_correct_functions(self):
        """
        The correct functions must be created on the MetricGenerator according
        to the settings in the settings file.
        """
        for msg_type in settings.MSG_TYPES:
            self.assertTrue(callable(getattr(
                MetricGenerator(),
                'registrations_msg_type_{}_sum'.format(msg_type))))

    def test_registrations_msg_type_total_last(self):
        """
        Should return the amount of registrations before the end of the
        timeframe for the given message type.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_type='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_type='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_type='type1')  # After

        reg_count = MetricGenerator().registrations_msg_type_total_last(
            'type1', start, end)
        self.assertEqual(reg_count, 3)

    def test_registrations_msg_type_total_last_correct_functions(self):
        """
        The correct functions must be created on the MetricGenerator according
        to the settings in the settings file.
        """
        for msg_type in settings.MSG_TYPES:
            self.assertTrue(callable(getattr(
                MetricGenerator(),
                'registrations_msg_type_{}_total_last'.format(msg_type))))

    def test_registrations_receiver_type_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific receiver type.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_receiver='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, msg_receiver='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_receiver='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_receiver='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_receiver='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_receiver='type1')  # After

        reg_count = MetricGenerator().registrations_receiver_type_sum(
            'type1', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_receiver_type_sum_correct_functions(self):
        """
        The correct functions must be created on the MetricGenerator according
        to the settings in the settings file.
        """
        for receiver_type in settings.RECEIVER_TYPES:
            self.assertTrue(callable(getattr(
                MetricGenerator(),
                'registrations_receiver_type_{}_sum'.format(receiver_type))))


class SendMetricTests(TestCase):
    @mock.patch('pika.BlockingConnection')
    def test_send_metric(self, mock_BlockingConnection):
        """
        The send metric function should create a connection to the AMQP server
        and publish the correct message to the correct exchange, then close
        the connection.
        """
        url = 'amqp://guest:guest@localhost:5672/%2F'
        send_metric(url, '', 'foo.bar', 17, datetime.utcfromtimestamp(1317))

        [urlparams], _ = mock_BlockingConnection.call_args
        self.assertEqual(urlparams.host, 'localhost')
        self.assertEqual(urlparams.port, 5672)
        self.assertEqual(urlparams.virtual_host, '/')
        self.assertEqual(urlparams.credentials.username, 'guest')
        self.assertEqual(urlparams.credentials.password, 'guest')

        connection = mock_BlockingConnection.return_value
        connection.channel.assert_called_once()
        connection.close.assert_called_once()

        channel = connection.channel.return_value
        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')

    @mock.patch('pika.BlockingConnection')
    def test_send_metric_prefix(self, mock_BlockingConnection):
        """
        The send_metric function should add the correct prefix tot he metric
        name that it sends.
        """
        url = 'amqp://guest:guest@localhost:5672/%2F'
        send_metric(
            url, 'test.prefix', 'foo.bar', 17, datetime.utcfromtimestamp(1317))

        connection = mock_BlockingConnection.return_value
        channel = connection.channel.return_value
        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'test.prefix.foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')
