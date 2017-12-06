""" This command creates Sites, SiteThemes, SiteConfigurations and partners."""
from __future__ import unicode_literals

import os
import json
import fnmatch
import logging

from oscar.core.loading import get_model
from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from ecommerce.theming.models import SiteTheme
from ecommerce.core.models import SiteConfiguration

logger = logging.getLogger(__name__)
Partner = get_model('partner', 'Partner')


class Command(BaseCommand):
    """Creates Sites, SiteThemes, SiteConfigurations and partners."""

    help = 'Creates Sites, SiteThemes, SiteConfigurations and partners.'
    dns_name = None
    theme_path = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--dns-name",
            type=str,
            help="Enter DNS name of sandbox.",
            required=True
        )

        parser.add_argument(
            "--theme-path",
            type=str,
            help="Enter theme directory path",
            required=True
        )

    def _create_sites(self, site_domain, theme_dir_name, site_configuration, partner_code):
        """
        Create Sites, SiteThemes and SiteConfigurations
        """
        site, _ = Site.objects.get_or_create(
            domain=site_domain,
            defaults={"name": theme_dir_name}
        )

        logger.info("Creating '{site_name}' SiteTheme".format(site_name=site_domain))
        SiteTheme.objects.get_or_create(
            site=site,
            theme_dir_name=theme_dir_name
        )

        logger.info("Creating '{partner}' Partner".format(partner=site_domain))
        partner, _ = Partner.objects.get_or_create(
            short_code=partner_code,
            defaults={
                "name": partner_code
            }
        )

        logger.info("Creating '{site_name}' SiteConfiguration".format(site_name=site_domain))
        SiteConfiguration.objects.get_or_create(
            site=site,
            partner=partner,
            defaults=site_configuration
        )

    def find(self, pattern, path):
        """
        Matched the given pattern in given path and returns the list of matching files
        """
        result = []
        for root, dirs, files in os.walk(path):  # pylint: disable=unused-variable
            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    result.append(os.path.join(root, name))
        return result

    def _get_site_partner_data(self):
        """
        Reads the json files from theme directory and returns the site partner data in JSON format.
        """
        site_data = {}
        for config_file in self.find('sandbox_configuration.json', self.theme_path):
            logger.info("Reading file from {file_name}".format(file_name=config_file))
            configuration_data = json.loads(
                json.dumps(
                    json.load(
                        open(config_file)
                    )
                ).replace("{dns_name}", self.dns_name)
            )['ecommerce_configuration']

            site_data[configuration_data['site_partner']] = {
                "partner_code": configuration_data['site_partner'],
                "site_domain": configuration_data['site_domain'],
                "theme_dir_name": configuration_data['theme_dir_name'],
                "configuration": configuration_data['configuration']
            }
        return site_data

    def delete_all(self):
        Site.objects.all().delete()
        SiteTheme.objects.all().delete()
        Partner.objects.all().delete()
        SiteConfiguration.objects.all().delete()
        self.print_all()

    def print_all(self):
        logger.info('------------------PARTNERS------------------')
        for partner in Partner.objects.all():
            logger.info(partner.__dict__)

        logger.info("------------------SITES------------------")
        for site in Site.objects.all():
            logger.info(site.__dict__)

        logger.info("------------------SITES THEMES------------------")
        for site in SiteTheme.objects.all():
            logger.info(site.__dict__)

        logger.info('------------------CONFIG------------------')
        for con in SiteConfiguration.objects.all():
            logger.info(con.__dict__)

    def handle(self, *args, **options):
        self.dns_name = options['dns_name']
        self.theme_path = options['theme_path']

        logger.info("DNS name: '{dns_name}'".format(dns_name=self.dns_name))
        logger.info("Theme path: '{theme_path}'".format(theme_path=self.theme_path))

        all_sites = self._get_site_partner_data()
        for site_name, site_data in all_sites.items():
            logger.info("Creating '{site_name}' Site".format(site_name=site_name))
            self._create_sites(
                site_data['site_domain'],
                site_data['theme_dir_name'],
                site_data['configuration'],
                site_data['partner_code']
            )
