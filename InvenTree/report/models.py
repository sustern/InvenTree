"""
Report template model definitions
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys

import datetime

from django.db import models
from django.conf import settings

from django.core.validators import FileExtensionValidator

import stock.models

from InvenTree.helpers import validateFilterString

from django.utils.translation import gettext_lazy as _

try:
    from django_weasyprint import WeasyTemplateResponseMixin
except OSError as err:
    print("OSError: {e}".format(e=err))
    print("You may require some further system packages to be installed.")
    sys.exit(1)


def rename_template(instance, filename):

    return instance.rename_file(filename)


def validate_stock_item_report_filters(filters):

    return validateFilterString(filters, model=stock.models.StockItem)


class WeasyprintReportMixin(WeasyTemplateResponseMixin):
    """
    Class for rendering a HTML template to a PDF.
    """

    pdf_filename = 'report.pdf'
    pdf_attachment = True

    def __init__(self, request, template, **kwargs):

        self.request = request
        self.template_name = template
        self.pdf_filename = kwargs.get('filename', 'report.pdf')


class ReportBase(models.Model):
    """
    Base class for uploading html templates
    """

    class Meta:
        abstract = True

    def __str__(self):
        return "{n} - {d}".format(n=self.name, d=self.description)

    def getSubdir(self):
        return ''

    def rename_file(self, filename):
        # Function for renaming uploaded file

        filename = os.path.basename(filename)

        return os.path.join('report', 'report_template', self.getSubdir(), filename)

    @property
    def extension(self):
        return os.path.splitext(self.template.name)[1].lower()

    @property
    def template_name(self):
        """
        Returns the file system path to the template file.
        Required for passing the file to an external process
        """

        template = self.template.name
        template = template.replace('/', os.path.sep)
        template = template.replace('\\', os.path.sep)

        template = os.path.join(settings.MEDIA_ROOT, template)

        return template

    name = models.CharField(
        blank=False, max_length=100,
        verbose_name=_('Name'),
        help_text=_('Template name'),
    )

    template = models.FileField(
        upload_to=rename_template,
        verbose_name=_('Template'),
        help_text=_("Report template file"),
        validators=[FileExtensionValidator(allowed_extensions=['html', 'htm'])],
    )

    description = models.CharField(
        max_length=250,
        verbose_name=_('Description'),
        help_text=_("Report template description")
    )


class ReportTemplateBase(ReportBase):
    """
    Reporting template model.

    Able to be passed context data

    """

    def get_context_data(self, request):
        """
        Supply context data to the template for rendering
        """

        return {}

    def render(self, request, **kwargs):
        """
        Render the template to a PDF file.

        Uses django-weasyprint plugin to render HTML template against Weasyprint
        """

        # TODO: Support custom filename generation!
        # filename = kwargs.get('filename', 'report.pdf')

        context = self.get_context_data(request)

        context['media'] = settings.MEDIA_ROOT

        context['report_name'] = self.name
        context['report_description'] = self.description
        context['request'] = request
        context['user'] = request.user
        context['date'] = datetime.datetime.now().date()
        context['datetime'] = datetime.datetime.now()

        # Render HTML template to PDF
        wp = WeasyprintReportMixin(
            request,
            self.template_name,
            base_url=request.build_absolute_uri("/"),
            presentational_hints=True,
            **kwargs)

        return wp.render_to_response(
            context,
            **kwargs)

    enabled = models.BooleanField(
        default=True,
        verbose_name=_('Enabled'),
        help_text=_('Report template is enabled'),
    )

    class Meta:
        abstract = True


class TestReport(ReportTemplateBase):
    """
    Render a TestReport against a StockItem object.
    """

    def getSubdir(self):
        return 'test'

    # Requires a stock_item object to be given to it before rendering
    stock_item = None

    filters = models.CharField(
        blank=True,
        max_length=250,
        verbose_name=_('Filters'),
        help_text=_("Part query filters (comma-separated list of key=value pairs)"),
        validators=[
            validate_stock_item_report_filters
        ]
    )

    def matches_stock_item(self, item):
        """
        Test if this report template matches a given StockItem objects
        """

        filters = validateFilterString(self.filters)

        items = stock.models.StockItem.objects.filter(**filters)

        # Ensure the provided StockItem object matches the filters
        items = items.filter(pk=item.pk)

        return items.exists()

    def get_context_data(self, request):
        return {
            'stock_item': self.stock_item,
            'part': self.stock_item.part,
            'results': self.stock_item.testResultMap(),
            'result_list': self.stock_item.testResultList()
        }


def rename_snippet(instance, filename):

    filename = os.path.basename(filename)

    return os.path.join('report', 'snippets', filename)


class ReportSnippet(models.Model):
    """
    Report template 'snippet' which can be used to make templates
    that can then be included in other reports.

    Useful for 'common' template actions, sub-templates, etc
    """

    snippet = models.FileField(
        upload_to=rename_snippet,
        help_text=_('Report snippet file'),
        validators=[FileExtensionValidator(allowed_extensions=['html', 'htm'])],
    )

    description = models.CharField(max_length=250, help_text=_("Snippet file description"))


def rename_asset(instance, filename):

    filename = os.path.basename(filename)

    return os.path.join('report', 'assets', filename)


class ReportAsset(models.Model):
    """
    Asset file for use in report templates.
    For example, an image to use in a header file.
    Uploaded asset files appear in MEDIA_ROOT/report/assets,
    and can be loaded in a template using the {% report_asset <filename> %} tag.
    """

    def __str__(self):
        return os.path.basename(self.asset.name)

    asset = models.FileField(
        upload_to=rename_asset,
        help_text=_("Report asset file"),
    )

    description = models.CharField(max_length=250, help_text=_("Asset file description"))
