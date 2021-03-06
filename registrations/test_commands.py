import responses
try:
    import mock
except ImportError:
    from unittest import mock

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from django.core import management

from .models import Registration, SubscriptionRequest
from .tests import AuthenticatedAPITestCase, REG_DATA


class ManagementCommandsTests(AuthenticatedAPITestCase):
    def test_command_requires_sbm_url(self):
        with self.assertRaises(management.CommandError) as ce:
            management.call_command("repopulate_subscriptions")
        self.assertEqual(
            str(ce.exception), "Please make sure either the "
            "STAGE_BASED_MESSAGING_URL environment variable or --sbm-url is "
            "set.")

    def test_command_requires_sbm_token(self):
        with self.assertRaises(management.CommandError) as ce:
            management.call_command("repopulate_subscriptions",
                                    sbm_url="http://example.com")
        self.assertEqual(
            str(ce.exception), "Please make sure either the "
            "STAGE_BASED_MESSAGING_TOKEN environment variable or --sbm-token "
            "is set.")

    @responses.activate
    @mock.patch("registrations.tasks.validate_registration.apply_async")
    def test_command_successful(self, mock_validation):
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration = Registration.objects.create(**registration_data)
        self.assertFalse(SubscriptionRequest.objects.all().exists())

        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/?identity=%s' %
            registration.mother_id,
            json={
                "next": None,
                "previous": None,
                "results": []
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

        management.call_command("repopulate_subscriptions",
                                sbm_url="http://localhost:8005/api/v1",
                                sbm_token="test_token")
        mock_validation.assert_called_once_with(
            kwargs={"registration_id": str(registration.id)})

    @mock.patch("registrations.tasks.validate_registration.apply_async")
    def test_command_subscription_requests_found(self, mock_validation):
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration = Registration.objects.create(**registration_data)
        SubscriptionRequest.objects.create(
            identity=str(registration.mother_id), messageset=3,
            next_sequence_number=2, lang="eng_ZA")

        management.call_command("repopulate_subscriptions",
                                sbm_url="http://localhost:8005/api/v1",
                                sbm_token="test_token")
        mock_validation.assert_not_called()

    @responses.activate
    @mock.patch("registrations.tasks.validate_registration.apply_async")
    def test_command_subscriptions_found(self, mock_validation):
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration = Registration.objects.create(**registration_data)
        self.assertFalse(SubscriptionRequest.objects.all().exists())

        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/?identity=%s' %
            registration.mother_id,
            json={
                "next": None,
                "previous": None,
                "results": [{
                    "id": "b0afe9fb-0b4d-478e-974e-6b794e69cc6e",
                    "version": 1,
                    "identity": "mother00-9d89-4aa6-99ff-13c225365b5d",
                    "messageset": 1,
                    "next_sequence_number": 1,
                    "lang": "eng",
                    "active": True,
                    "completed": False,
                    "schedule": 1,
                    "process_status": 0,
                    "metadata": None,
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

        management.call_command("repopulate_subscriptions",
                                sbm_url="http://localhost:8005/api/v1",
                                sbm_token="test_token")
        mock_validation.assert_not_called()

    @responses.activate
    @mock.patch("registrations.tasks.validate_registration.apply_async")
    def test_command_query_given(self, mock_validation):
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration1 = Registration.objects.create(**registration_data)
        registration_data = {
            "stage": "postbirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_post"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        Registration.objects.create(**registration_data)
        self.assertFalse(SubscriptionRequest.objects.all().exists())

        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/?identity=%s' %
            registration1.mother_id,
            json={
                "next": None,
                "previous": None,
                "results": []
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

        management.call_command("repopulate_subscriptions",
                                sbm_url="http://localhost:8005/api/v1",
                                sbm_token="test_token",
                                reg_query="stage:prebirth")
        mock_validation.assert_called_once_with(
            kwargs={"registration_id": str(registration1.id)})


class UpdateInitialSequenceCommand(AuthenticatedAPITestCase):
    def test_command_requires_sbm_url(self):
        with self.assertRaises(management.CommandError) as ce:
            management.call_command("update_initial_sequence")
        self.assertEqual(
            str(ce.exception), "Please make sure either the "
            "STAGE_BASED_MESSAGING_URL environment variable or --sbm-url is "
            "set.")

    def test_command_requires_sbm_token(self):
        with self.assertRaises(management.CommandError) as ce:
            management.call_command("update_initial_sequence",
                                    sbm_url="http://example.com")
        self.assertEqual(
            str(ce.exception), "Please make sure either the "
            "STAGE_BASED_MESSAGING_TOKEN environment variable or --sbm-token "
            "is set.")

    @responses.activate
    def test_update_initial_sequence(self):
        stdout, stderr = StringIO(), StringIO()
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration = Registration.objects.create(**registration_data)

        SubscriptionRequest.objects.create(
            identity=str(registration.mother_id), messageset=3,
            next_sequence_number=2, lang="eng_ZA")

        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/',
            json={
                "next": None,
                "previous": None,
                "results": [{
                    "id": "b0afe9fb-0b4d-478e-974e-6b794e69cc6e",
                    "version": 1,
                    "identity": "mother00-9d89-4aa6-99ff-13c225365b5d",
                    "messageset": 1,
                    "next_sequence_number": 1,
                    "lang": "eng",
                    "active": True,
                    "completed": False,
                    "schedule": 1,
                    "process_status": 0,
                    "metadata": None,
                    "created_at": "2017-01-16",
                }]
            },
            status=200, content_type='application/json',
            match_querystring=False
        )

        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/b0afe9fb-0b4d-478e-974e-6b794e69cc6e/',  # noqa
            json={"active": False},
            status=200, content_type='application/json',
            match_querystring=True
        )

        management.call_command("update_initial_sequence",
                                sbm_url="http://localhost:8005/api/v1",
                                sbm_token="test_token",
                                stdout=stdout, stderr=stderr)

        self.assertEqual(stderr.getvalue(), '')
        self.assertEqual(stdout.getvalue().strip(), 'Updated 1 subscriptions.')

    @responses.activate
    def test_update_initial_sequence_no_sub(self):
        stdout, stderr = StringIO(), StringIO()
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration = Registration.objects.create(**registration_data)

        SubscriptionRequest.objects.create(
            identity=str(registration.mother_id), messageset=3,
            next_sequence_number=2, lang="eng_ZA")

        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/',
            json={
                "next": None,
                "previous": None,
                "results": []
            },
            status=200, content_type='application/json',
            match_querystring=False
        )

        management.call_command("update_initial_sequence",
                                sbm_url="http://localhost:8005/api/v1",
                                sbm_token="test_token",
                                stdout=stdout, stderr=stderr)

        self.assertEqual(stderr.getvalue(), '')
        self.assertEqual(stdout.getvalue().strip(),
                         'Subscription not found: mother00-9d89-4aa6-99ff-'
                         '13c225365b5d\nUpdated 0 subscriptions.')
