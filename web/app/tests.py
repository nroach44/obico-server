from django.test import TestCase
from unittest.mock import patch


from .models import User, HeaterTracker, Printer
from .heater_trackers import update_heater_trackers


class HeaterTrackerTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(email="a@test")
        self.printer = Printer.objects.create(user=self.user)

    def test_not_created_without_target(self):
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 50.0, 'target': None, 'offset': 0}}
        )

        self.assertIsNone(self.printer.heatertracker_set.first())

    def test_created_when_has_target(self):
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 50.0, 'target': 0.0, 'offset': 0}}
        )

        self.assertEqual(self.printer.heatertracker_set.first().target, 0.0)

    def test_updated_when_target_changes(self):
        tracker = HeaterTracker.objects.create(
            printer=self.printer, name='h0', target=0.0, reached=False)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 50.0, 'target': 100.0, 'offset': 0}}
        )

        tracker.refresh_from_db()
        self.assertEqual(tracker.target, 100.0)

    def test_deleted_when_obsolete(self):
        HeaterTracker.objects.create(
            printer=self.printer, name='h0', target=0.0, reached=False)
        HeaterTracker.objects.create(
            printer=self.printer, name='h1', target=200.0, reached=False)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 50.0, 'target': None, 'offset': 0}}
            # h1 is no longer exists in data
        )

        self.assertEqual(self.printer.heatertracker_set.count(), 0)

    @patch("app.heater_trackers.send_heater_event")
    def test_cooled_down_threshold(self, mock_send):
        calls = []

        def call(*args, **kwargs):
            calls.append((args, kwargs))

        mock_send.side_effect = call

        HeaterTracker.objects.create(
            printer=self.printer, name='h0', target=0.0, reached=False)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 36.0, 'target': 0.0, 'offset': 0}}
        )

        self.assertIs(self.printer.heatertracker_set.first().reached, False)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 35.0, 'target': 0.0, 'offset': 0}}
        )

        self.assertIs(self.printer.heatertracker_set.first().reached, True)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]['event'], 'cooled down')

    @patch("app.heater_trackers.send_heater_event")
    def test_target_reached_delta(self, mock_send):
        calls = []

        def call(*args, **kwargs):
            calls.append((args, kwargs))

        mock_send.side_effect = call

        HeaterTracker.objects.create(
            printer=self.printer, name='h0', target=60.0, reached=False)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 57.0, 'target': 60.0, 'offset': 0}}
        )

        self.assertIs(self.printer.heatertracker_set.first().reached, False)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 58.0, 'target': 60.0, 'offset': 0}}
        )

        self.assertIs(self.printer.heatertracker_set.first().reached, True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]['event'], 'target reached')

    @patch("app.heater_trackers.send_heater_event")
    def test_no_events_after_reached(self, mock_send):
        calls = []

        def call(*args, **kwargs):
            calls.append((args, kwargs))

        mock_send.side_effect = call

        HeaterTracker.objects.create(
            printer=self.printer, name='h0', target=60.0, reached=True)

        # -delta
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 58.0, 'target': 60.0, 'offset': 0}}
        )

        # +delta
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 62.0, 'target': 60.0, 'offset': 0}}
        )

        # -whatever
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 70.0, 'target': 60.0, 'offset': 0}}
        )

        # +whatever
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 50.0, 'target': 60.0, 'offset': 0}}
        )

        self.assertEqual(len(calls), 0)
        self.assertIs(self.printer.heatertracker_set.first().reached, True)

    @patch("app.heater_trackers.send_heater_event")
    def test_first_seen_reached_event(self, mock_send):
        calls = []

        def call(*args, **kwargs):
            calls.append((args, kwargs))

        mock_send.side_effect = call

        # very first gets reached if target is in actual+-delta
        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 60.0, 'target': 60.0, 'offset': 0}}
        )

        self.assertIs(self.printer.heatertracker_set.first().reached, True)
        self.assertEqual(len(calls), 1)

    @patch("app.heater_trackers.send_heater_event")
    def test_target_changes_and_reached_event(self, mock_send):
        calls = []

        def call(*args, **kwargs):
            calls.append((args, kwargs))

        mock_send.side_effect = call

        HeaterTracker.objects.create(
            printer=self.printer, name='h0', target=60.0, reached=True)

        update_heater_trackers(
            self.printer,
            {'h0': {'actual': 70.0, 'target': 70.0, 'offset': 0}}
        )

        self.assertIs(self.printer.heatertracker_set.first().reached, True)
        self.assertEqual(len(calls), 1)
