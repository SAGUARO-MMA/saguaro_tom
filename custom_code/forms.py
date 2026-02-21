from django import forms
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from crispy_forms.bootstrap import AppendedText, PrependedAppendedText
from tom_targets.models import TargetList
from tom_dataproducts.models import ReducedDatum
from .models import TargetListExtra
from datetime import datetime, timezone
from io import StringIO
import numpy as np
import json
import os


TargetListExtraFormset = inlineformset_factory(TargetList, TargetListExtra, fields=('key', 'value'),
                                               widgets={'value': forms.TextInput()})

TNS_FILTER_CHOICES = [
    ('', ''),
    (0, "Other"),
    (1, "Clear"),
    (10, "U-Johnson"),
    (11, "B-Johnson"),
    (12, "V-Johnson"),
    (13, "R-Cousins"),
    (14, "I-Cousins"),
    (15, "J-Bessel"),
    (16, "H-Bessel"),
    (17, "K-Bessel"),
    (18, "L"),
    (19, "M"),
    (20, "u-Sloan"),
    (21, "g-Sloan"),
    (22, "r-Sloan"),
    (23, "i-Sloan"),
    (24, "z-Sloan"),
    (25, "y-P1"),
    (26, "w-P1"),
    (71, "cyan-ATLAS"),
    (72, "orange-ATLAS"),
    (73, "wide-ATLAS"),
    (110, "g-ZTF"),
    (111, "r-ZTF"),
    (112, "i-ZTF"),
    (160, "u-LSST"),
    (161, "g-LSST"),
    (162, "r-LSST"),
    (163, "i-LSST"),
    (164, "z-LSST"),
    (165, "y-LSST"),
]

TNS_INSTRUMENT_CHOICES = [
    (3, "Keck1 - LRIS"),
    (4, "Keck2 - DEIMOS"),
    (6, "Gemini-N - GMOS"),
    (9, "Gemini-S - GMOS-S"),
    (10, "Lick-3m - KAST"),
    (43, "HET - HET-LRS"),
    (44, "FLWO-1.5m - FAST"),
    (58, "MMT - MMT-Blue"),
    (68, "Bok - BC-Bok"),
    (70, "APO-3.5m - DIS"),
    (75, "Magellan-Baade - IMACS"),
    (78, "Magellan-Clay - LDSS-3"),
    (82, "Keck1 - HIRES"),
    (83, "Magellan-Clay - MIKE"),
    (96, "MMT - Hectospec"),
    (100, "Keck2 - ESI"),
    (107, "Lijiang-2.4m - YFOSC"),
    (108, "FTN - FLOYDS-N"),
    (115, "ANU-2.3m - WiFeS"),
    (116, "Magellan-Baade - FIRE"),
    (117, "SALT - RSS"),
    (118, "SALT - HRS-SALT"),
    (120, "LBT - MODS1"),
    (121, "LBT - MODS2"),
    (122, "IRTF - SpeX"),
    (123, "HET - HET-HRS"),
    (124, "HET - HET-MRS"),
    (125, "FTS - FLOYDS-S"),
    (127, "SOAR - Goodman"),
    (130, "Keck1 - MOSFIRE"),
    (137, "Magellan-Baade - MagE"),
    (141, "APO-3.5m - APO-TSPEC"),
    (159, "ATLAS-HKO - ATLAS-02"),
    (160, "ATLAS-MLO - ATLAS-01"),
    (166, "Gemini-N - GNIRS"),
    (180, "MMT - MMIRS"),
    (196, "P48 - ZTF-Cam"),
    (197, "Gemini-S - Flamingos-2"),
    (172, "CTIO-4m - DECAM"),
    (208, "LCO1m - Sinistro"),
    (221, "MMT - BINOSPEC"),
    (252, "Keck2 - NIRES"),
    (255, "ATLAS-STH - ATLAS-03"),
    (256, "ATLAS-CHL - ATLAS-04"),
    (259, "Keck2 - KCWI"),
    (260, "SOAR - TripleSpec"),
    (287, "Rubin - LSSTCam"),
    (290, "ATLAS-TDO - ATLAS-05"),
]
TNS_INSTRUMENT_CHOICES.sort(key=lambda x: x[1])
TNS_INSTRUMENT_CHOICES.insert(0, ('', ''))
TNS_INSTRUMENT_CHOICES.insert(1, (0, "Other"))

TNS_CLASSIFICATION_CHOICES = [
    (0, "Other"),
    (1, "SN"),
    (2, "SN I"),
    (3, "SN Ia"),
    (4, "SN Ib"),
    (5, "SN Ic"),
    (6, "SN Ib/c"),
    (7, "SN Ic-BL"),
    (9, "SN Ibn"),
    (10, "SN II"),
    (11, "SN IIP"),
    (12, "SN IIL"),
    (13, "SN IIn"),
    (14, "SN IIb"),
    (15, "SN I-faint"),
    (16, "SN I-rapid"),
    (18, "SLSN-I"),
    (19, "SLSN-II"),
    (20, "SLSN-R"),
    (23, "Afterglow"),
    (24, "LBV"),
    (25, "ILRT"),
    (26, "Nova"),
    (27, "CV"),
    (28, "Varstar"),
    (29, "AGN"),
    (30, "Galaxy"),
    (31, "QSO"),
    (40, "Light-Echo"),
    (50, "Std-spec"),
    (60, "Gap"),
    (61, "Gap I"),
    (62, "Gap II"),
    (65, "LRN"),
    (66, "FBOT"),
    (70, "Kilonova"),
    (99, "Impostor-SN"),
    (100, "SN Ia-pec"),
    (102, "SN Ia-SC"),
    (103, "SN Ia-91bg-like"),
    (104, "SN Ia-91T-like"),
    (105, "SN Iax[02cx-like]"),
    (106, "SN Ia-CSM"),
    (107, "SN Ib-pec"),
    (108, "SN Ic-pec"),
    (109, "SN Icn"),
    (110, "SN Ibn/Icn"),
    (111, "SN II-pec"),
    (112, "SN IIn-pec"),
    (115, "SN Ib-Ca-rich"),
    (116, "SN Ib/c-Ca-rich"),
    (117, "SN Ic-Ca-rich"),
    (118, "SN Ia-Ca-rich"),
    (120, "TDE"),
    (121, "TDE-H"),
    (122, "TDE-He"),
    (123, "TDE-H-He"),
    (200, "WR"),
    (201, "WR-WN"),
    (202, "WR-RC"),
    (203, "WR-WO"),
    (210, "M dwarf"),
]

TNS_GROUP_CHOICES = [
    (30, "DLT40"),
    (38, "Global SN Project"),
    (52, "AZTEC"),
    (66, "SAGUARO"),
    (176, "TROVE"),
    (177, "PASSTA"),
    (178, "Shadow"),
]

TNS_DATA_SOURCE_GROUP_CHOICES = TNS_GROUP_CHOICES + [
    (18, "ATLAS"),
    (49, "ZTF"),
    (165, "Rubin"),
]

TNS_GROUP_CHOICES.sort(key=lambda x: x[1])
TNS_GROUP_CHOICES.insert(0, (0, "None"))
TNS_DATA_SOURCE_GROUP_CHOICES.sort(key=lambda x: x[1])
TNS_DATA_SOURCE_GROUP_CHOICES.insert(0, (0, "None"))

TNS_UNIT_CHOICES = [
    (0, "Other"),
    (1, "ABMag"),
    (2, "STMag"),
    (3, "VegaMag"),
    (4, "erg cm(-2) sec(-1)"),
    (5, "erg cm(-2) sec(-1) Hz(-1)"),
    (6, "erg cm(-2) sec(-1) Ang(-1)"),
    (7, "counts sec(-1)"),
    (8, "Jy"),
    (9, "mJy"),
    (10, "Neutrino events"),
    (33, "Photons sec(-1) cm(-2)"),
]


class TargetReportForm(forms.Form):
    # discovery
    ra = forms.FloatField(label='R.A.')
    dec = forms.FloatField(label='Dec.')
    reporting_group = forms.ChoiceField(choices=TNS_GROUP_CHOICES)
    data_source_group = forms.ChoiceField(choices=TNS_DATA_SOURCE_GROUP_CHOICES)
    reporter = forms.CharField(widget=forms.Textarea(attrs={'rows': 1}),
                               help_text="FirstName1 LastName1 (Affil1), FirstName2 LastName2 (Affil2), &hellip;, "
                                         "on behalf of SurveyName (optional)")
    discovery_date = forms.DateTimeField(initial=datetime.now(timezone.utc))
    at_type = forms.ChoiceField(choices=[
        (0, "Other - Undefined"),
        (1, "PSN - Possible SN"),
        (2, "PNV - Possible Nova"),
        (3, "AGN - Known AGN"),
        (4, "NUC - Possibly nuclear"),
        (5, "FRB - Fast Radio Burst"),
    ], initial=(1, "PSN"), label='AT type')
    host_name = forms.CharField(required=False)
    host_redshift = forms.FloatField(required=False)
    internal_name = forms.CharField(required=False)
    discovery_remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 1}))

    # nondetection
    nondetection_date = forms.DateTimeField(required=False, label='Observation date')
    nondetection_limit = forms.FloatField(required=False, label='Limiting flux')
    nondetection_units = forms.ChoiceField(choices=TNS_UNIT_CHOICES, label='Flux units', initial=(1, "ABMag"), required=False)
    nondetection_filter = forms.ChoiceField(choices=TNS_FILTER_CHOICES, label='Filter', required=False)
    nondetection_instrument = forms.ChoiceField(choices=TNS_INSTRUMENT_CHOICES, label='Instrument', required=False)
    nondetection_observer = forms.CharField(label='Observer', required=False)
    archive = forms.ChoiceField(choices=[
        ('', ''),
        (0, "Other"),
        (1, "SDSS"),
        (2, "DSS"),
    ], help_text="Required if no nondetection", required=False)
    archival_remarks = forms.CharField(help_text='Required if "Other"', required=False)
    nondetection_remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 1}))

    # photometry
    observation_date = forms.DateTimeField()
    flux = forms.FloatField()
    flux_error = forms.FloatField(required=False)
    limiting_flux = forms.FloatField(required=False)
    flux_units = forms.ChoiceField(choices=TNS_UNIT_CHOICES, initial=(1, "ABMag"))
    filter = forms.ChoiceField(choices=TNS_FILTER_CHOICES)
    instrument = forms.ChoiceField(choices=TNS_INSTRUMENT_CHOICES)
    exposure_time = forms.FloatField(required=False)
    observer = forms.CharField(required=False)
    photometry_remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 1}))

    send_to_sandbox = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('reporter', css_class='col-md-9'),
                Column('reporting_group'),
            ),
            Row(
                Column(AppendedText('ra', 'deg')),
                Column(AppendedText('dec', 'deg')),
                Column('discovery_date'),
                Column('at_type'),
            ),
            Row(
                Column('host_name'),
                Column('host_redshift'),
                Column('internal_name'),
                Column('data_source_group'),
            ),
            Row(Column('discovery_remarks')),
            Row(HTML('<h4>Discovery Photometry</h4>')),
            Row(
                Column('observation_date'),
                Column('instrument'),
                Column('limiting_flux'),
                Column('observer'),
            ),
            Row(
                Column('flux'),
                Column('flux_error'),
                Column('flux_units'),
                Column('filter'),
            ),
            Row(Column('photometry_remarks')),
            Row(HTML('<h4>Last Nondetection</h4>')),
            Row(
                Column('nondetection_date'),
                Column('nondetection_instrument'),
                Column('nondetection_limit'),
                Column('nondetection_observer'),
            ),
            Row(
                Column('archive'),
                Column('archival_remarks'),
                Column('nondetection_units'),
                Column('nondetection_filter'),
            ),
            Row(
                Column('nondetection_remarks'),
            ),
            Row(Column(Submit('submit', 'Submit Report'), 'send_to_sandbox')),
        )

    def generate_tns_report(self):
        """
        Generate TNS bulk transient report according to the schema in this manual:
        https://sandbox.wis-tns.org/sites/default/files/api/TNS_bulk_reports_manual.pdf

        Returns the report as a JSON-formatted string
        """
        report_data = {
            "at_report": {
                "0": {
                    "ra": {
                        "value": self.cleaned_data['ra'],
                    },
                    "dec": {
                        "value": self.cleaned_data['dec'],
                    },
                    "reporting_groupid": self.cleaned_data['reporting_group'],
                    "data_source_groupid": self.cleaned_data['data_source_group'],
                    "reporter": self.cleaned_data['reporter'],
                    "discovery_datetime": self.cleaned_data['discovery_date'].isoformat(sep=' ', timespec='milliseconds')[:-6],
                    "at_type": self.cleaned_data['at_type'],
                    "host_name": self.cleaned_data['host_name'],
                    "host_redshift": self.cleaned_data['host_redshift'],
                    "internal_name": self.cleaned_data['internal_name'],
                    "non_detection": {
                        "obsdate": self.cleaned_data['nondetection_date'].isoformat(sep=' ', timespec='milliseconds')[:-6],
                        "limiting_flux": self.cleaned_data['nondetection_limit'],
                        "flux_unitid": self.cleaned_data['nondetection_units'],
                        "filterid": self.cleaned_data['nondetection_filter'],
                        "instrumentid": self.cleaned_data['nondetection_instrument'],
                        "observer": self.cleaned_data['nondetection_observer'],
                        "comments": self.cleaned_data['nondetection_remarks'],
                        "archiveid": self.cleaned_data['archive'],
                        "archival_remarks": self.cleaned_data['archival_remarks'],
                    },
                    "photometry": {
                        "photometry_group": {
                            "0": {
                                "obsdate": self.cleaned_data['observation_date'].isoformat(sep=' ', timespec='milliseconds')[:-6],
                                "flux": self.cleaned_data['flux'],
                                "flux_error": self.cleaned_data['flux_error'],
                                "limiting_flux": self.cleaned_data['limiting_flux'],
                                "flux_unitid": self.cleaned_data['flux_units'],
                                "filterid": self.cleaned_data['filter'],
                                "instrumentid": self.cleaned_data['instrument'],
                                "exptime": self.cleaned_data['exposure_time'],
                                "observer": self.cleaned_data['observer'],
                                "comments": self.cleaned_data['photometry_remarks'],
                            },
                        }
                    },
                }
            }
        }
        return json.dumps(report_data)


def _get_spectrum_choices(target):
    reduceddatums = target.reduceddatum_set.filter(data_type='spectroscopy').order_by('timestamp')
    choices = [(None, '-------')]
    for rd in reduceddatums:
        description = f'{rd.source_name} {rd.data_type} @ {rd.timestamp.isoformat(sep=" ", timespec="milliseconds")[:-6]} <ReducedDatum {rd.pk}>'
        choices.append((rd.pk, description))
    return choices


def reduced_datum_to_ascii_file(rd):
    """
    Create a virtual ASCII file from a spectrum ReducedDatum for upload to TNS
    """
    file_buffer = StringIO()
    timestring = rd.timestamp.isoformat(timespec="milliseconds")[:-6]
    header = (
        f"# OBJECT  = '{rd.target.name}'\n"
        f"# DATE-OBS= '{timestring}'\n"
    )
    if rd.source_name:
        header += f"# TELESCOP= '{rd.source_name}'\n"
    if 'flux_units' in rd.value:
        bunit = rd.value['flux_units']
        header += f"# BUNIT   = '{bunit}'\n"
    if 'wavelength_units' in rd.value:
        cunit = rd.value['wavelength_units']
        header += f"# CUNIT1  = '{cunit}'\n"
    file_buffer.write(header)
    output_spectrum = np.transpose([rd.value['wavelength'], rd.value['flux']])
    np.savetxt(file_buffer, output_spectrum, fmt=('%f', '%e'))
    file_buffer.seek(0)  # return to the beginning of the buffer
    if rd.data_product is not None:
        file_name = rd.data_product.get_file_name()
        if file_name.endswith('.fits') or file_name.endswith('.fits.fz'):
            file_name = file_name.rstrip('.fz').rstrip('.fits') + '.txt'
    else:
        file_name = f'saguaro_{rd.pk}.txt'
    return file_name, file_buffer, 'text/plain'


class TargetClassifyForm(forms.Form):
    name = forms.CharField()
    classifier = forms.CharField(widget=forms.Textarea(attrs={'rows': 1}),
                                 help_text="FirstName1 LastName1 (Affil1), FirstName2 LastName2 (Affil2), &hellip;, "
                                           "on behalf of SurveyName (optional)")
    classification = forms.ChoiceField(choices=TNS_CLASSIFICATION_CHOICES, initial=(1, "SN"))
    redshift = forms.FloatField(required=False)
    group = forms.ChoiceField(choices=TNS_GROUP_CHOICES)
    classification_remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 1}))
    observation_date = forms.DateTimeField()
    instrument = forms.ChoiceField(choices=TNS_INSTRUMENT_CHOICES)
    exposure_time = forms.FloatField(required=False)
    observer = forms.CharField()
    reducer = forms.CharField(required=False)
    spectrum_type = forms.ChoiceField(choices=[
        (1, 'Object'),
        (2, 'Host'),
        (3, 'Sky'),
        (4, 'Arcs'),
        (5, 'Synthetic'),
    ])
    spectrum = forms.TypedChoiceField(required=False,
                                      coerce=lambda pk: ReducedDatum.objects.get(pk=pk))
    ascii_file = forms.FileField(label='ASCII file', required=False,
                                 help_text='Uploading a file here overrides the ASCII file from the spectrum field')
    fits_file = forms.FileField(label='FITS file', required=False,
                                help_text='Uploading a file here overrides the FITS file from the spectrum field (if any)')
    spectrum_remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 1}))
    send_to_sandbox = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        target = kwargs.pop('target', None)
        super().__init__(*args, **kwargs)
        if target is not None:
            self.fields['spectrum'].choices = _get_spectrum_choices(target)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('classifier', css_class='col-md-8'),
                Column('group'),
            ),
            Row(
                Column('name'),
                Column('classification'),
                Column('redshift'),
            ),
            Row(Column('classification_remarks')),
            Row(HTML('<h4>Classification Spectrum</h4>')),
            Row(Column('spectrum')),
            Row(
                Column('observation_date'),
                Column('observer'),
                Column('reducer'),
            ),
            Row(
                Column('instrument'),
                Column('exposure_time'),
                Column('spectrum_type'),
            ),
            Row(
                Column('ascii_file'),
                Column('fits_file'),
            ),
            Row(Column('spectrum_remarks')),
            Row(Column(Submit('submit', 'Submit Report'), 'send_to_sandbox')),
        )

    def files_to_upload(self):
        files_to_upload = {}
        if self.cleaned_data['ascii_file']:
            files_to_upload['files[0]'] = (
                os.path.basename(self.cleaned_data['ascii_file'].name),
                self.cleaned_data['ascii_file'].open(),
                'text/plain'
            )
        elif self.cleaned_data['spectrum']:
            files_to_upload['files[0]'] = reduced_datum_to_ascii_file(self.cleaned_data['spectrum'])

        if self.cleaned_data['fits_file']:
            files_to_upload['files[1]'] = (
                os.path.basename(self.cleaned_data['fits_file'].name),
                self.cleaned_data['fits_file'].open(),
                'application/fits'
            )
        elif (self.cleaned_data['spectrum']
              and self.cleaned_data['spectrum'].data_product.get_file_extension() == '.fits'):
            fits_file = self.cleaned_data['spectrum'].data_product
            files_to_upload['files[1]'] = (fits_file.get_file_name(), fits_file.data.open(), 'application/fits')
        return files_to_upload

    def generate_tns_report(self, new_filenames=None):
        """
        Generate TNS bulk classification report according to the schema in this manual:
        https://sandbox.wis-tns.org/sites/default/files/api/TNS_bulk_reports_manual.pdf

        Returns the report as a JSON-formatted string
        """
        report_data = {
            "classification_report": {
                "0": {
                    "name": self.cleaned_data['name'],
                    "classifier": self.cleaned_data['classifier'],
                    "objtypeid": self.cleaned_data['classification'],
                    "redshift": self.cleaned_data['redshift'],
                    "groupid": self.cleaned_data['group'],
                    "remarks": self.cleaned_data['classification_remarks'],
                    "spectra": {
                        "0": {
                            "obsdate": self.cleaned_data['observation_date'].isoformat(sep=' ', timespec='milliseconds')[:-6],
                            "instrumentid": self.cleaned_data['instrument'],
                            "exptime": self.cleaned_data['exposure_time'],
                            "observer": self.cleaned_data['observer'],
                            "reducer": self.cleaned_data['reducer'],
                            "spectypeid": self.cleaned_data['spectrum_type'],
                            "remarks": self.cleaned_data['spectrum_remarks'],
                        },
                    },
                }
            }
        }
        if new_filenames:
            report_data['classification_report']['0']['spectra']['0']['ascii_file'] = new_filenames[0]
            if len(new_filenames) > 1:
                report_data['classification_report']['0']['spectra']['0']['fits_file'] = new_filenames[1]
        else:  # assuming they were previously uploaded
            files_to_upload = self.files_to_upload()
            if 'files[0]' in files_to_upload:
                report_data['classification_report']['0']['spectra']['0']['ascii_file'] = files_to_upload['files[0]'][0]
            if 'files[1]' in files_to_upload:
                report_data['classification_report']['0']['spectra']['0']['fits_file'] = files_to_upload['files[1]'][0]
        return json.dumps(report_data)


class NonLocalizedEventFormHelper(FormHelper):
    layout = Layout(
            Row(
                Column('prefix'),
                Column('state'),
                Column(PrependedAppendedText('inv_far_min', '>', 'yr')),
                # Column('classification'),
                Column(PrependedAppendedText('distance_max', '<', 'Mpc')),
                Column(PrependedAppendedText('has_ns_min', '>', '%')),
                Column(PrependedAppendedText('has_remnant_min', '>', '%')),
            ),
            Row(
                Column(
                    Submit('submit', 'Filter'),
                    HTML('<a href="{{ request.path }}" class="btn btn-secondary" title="Reset">Reset</a>'),
                    css_class='text-right',
                )
            )
        )


class CandidateFormHelper(FormHelper):
    layout = Layout(
        Row(
            Column('obsdate_range'),
            Column('mag_range'),
            Column('snr_range'),
            Column('mlscore_range'),
            Column('mlscore_real_range'),
            Column('mlscore_bogus_range'),
        ),
        Row(
            Column('target__name__startswith'),
            Column('cone_search'),
            Column('observation_record__survey_field'),
            Column('classification'),
            Column('localization'),
            Column('order'),
        ),
        Row(
            Column(
                Submit('submit', 'Filter'),
                HTML('<a href="{% url \'custom_code:candidates\' %}" class="btn btn-secondary" title="Reset">Reset</a>'),
                css_class='text-right',
            )
        )
    )
