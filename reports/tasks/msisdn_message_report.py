from django.conf import settings
from os.path import getsize
from reports.models import ReportTaskStatus
from reports.tasks.base import BaseTask
from reports.utils import ExportWorkbook, generate_random_filename
from seed_services_client import IdentityStoreApiClient


class GenerateMSISDNMessageReport(BaseTask):
    """
    Generate an Excel spreadsheet for a Pathfinder <http://www.pathfinder.org/>
    cohort study which includes details of messages sent to the specified
    MSISDNs.
    """

    def run(self, start_date, end_date, task_status_id, msisdns=[]):
        task_status = ReportTaskStatus.objects.get(id=task_status_id)
        task_status.status = ReportTaskStatus.RUNNING
        task_status.save()

        self.is_client = IdentityStoreApiClient(
            settings.IDENTITY_STORE_TOKEN,
            settings.IDENTITY_STORE_URL,
        )

        data = self.retrieve_identity_info(msisdns)

        spreadsheet = self.populate_spreadsheet(data)

        output_file = generate_random_filename()
        spreadsheet.save(output_file)

        task_status.status = ReportTaskStatus.SENDING
        task_status.file_size = getsize(output_file)
        task_status.save()

        # TODO: Use SendEmail task to send the email

    def retrieve_identity_info(self, msisdns):
        logger = self.get_logger()

        data = {}
        for msisdn in msisdns:
            response = self.is_client.get_identity_by_address('msisdn', msisdn)
            results = list(response['results'])

            if len(results) < 1:
                logger.info(
                    'No results from identity store for {0}'.format(msisdn))
                data[msisdn] = {}
                continue

            if len(results) > 1:
                logger.info(
                    'Multiple results from identity store for {0}'
                    .format(msisdn))
                data[msisdn] = {}
                continue

            data[msisdn] = {'id': results[0]['id'],
                            'created_at': results[0]['created_at']}

        return data

    def populate_spreadsheet(self, data):
        workbook = ExportWorkbook()
        sheet = workbook.add_sheet('Data for study cohort', 0)

        sheet.set_header([
            'Phone number',
            'Date registered',
            'Facility',
            'Pregnancy week',
            'Message type',
            'Message 1: content',
            'Message 1: date sent',
            'Message 1: status'
        ])

        for msisdn in data:
            sheet.add_row({
                'Phone number': msisdn,
                'Date registered': data[msisdn]['created_at']
            })

        return workbook


generate_msisdn_message_report = GenerateMSISDNMessageReport()