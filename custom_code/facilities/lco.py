from tom_observations.facilities.lco import LCOFacility, LCOPhotometricSequenceForm, LCOSpectroscopicSequenceForm
from tom_dataproducts.data_processor import run_data_processor, DataProcessor
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.utils import create_image_dataproduct
from tom_targets.models import Target
from astropy.coordinates import SkyCoord
from astropy.io import fits
from crispy_forms.layout import Row, Column
from crispy_forms.bootstrap import PrependedText
from django.core.files.base import ContentFile
from django.conf import settings
from django import forms
from datetime import datetime, timedelta
import requests
import mimetypes
import tarfile
import copy
import os
import logging

logger = logging.getLogger(__name__)


class CustomLCOSequenceFormMixin(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['start'] = forms.DateTimeField()
        self.fields['end'] = forms.DateTimeField()

        if 'target_id' in self.initial:
            self.initial['name'] = Target.objects.get(pk=self.initial['target_id']).name
        self.initial['cadence_strategy'] = 'ResumeCadenceAfterFailureStrategy'
        self.initial['cadence_frequency'] = 72.

        self.initial['max_airmass'] = 1.6
        self.initial['min_lunar_distance'] = 20.
        self.initial['proposal'] = 'KEY2026B-003'
        self.initial['ipp_value'] = 1.

    def clean_start(self):
        start = self.cleaned_data.get('start')
        if isinstance(start, datetime):
            start = start.isoformat()
        return start

    def clean_end(self):
        end = self.cleaned_data.get('end')
        if isinstance(end, datetime):
            end = end.isoformat()
        return end

    def clean(self):
        """
        Overrides the parent form behavior to use a maximum window of 24 hours
        """
        self.cleaned_data = super().clean()
        if not self.cleaned_data.get('end') and self.cleaned_data.get('start'):
            window_length = min(self.cleaned_data['cadence_frequency'], 24.)
            self.cleaned_data['end'] = self.cleaned_data['start'] + timedelta(hours=window_length)

        return self.cleaned_data


class CustomLCOPhotometricSequenceForm(CustomLCOSequenceFormMixin, LCOPhotometricSequenceForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['U'] = (300., 2, 1)
        self.initial['B'] = (200., 2, 1)
        self.initial['V'] = (120., 2, 1)
        self.initial['gp'] = (200., 2, 1)
        self.initial['rp'] = (120., 2, 1)
        self.initial['ip'] = (120., 2, 1)

    def all_optical_element_choices(self, use_code_only=False):
        return sorted(set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('filters', [])
            if f['code'] in LCOPhotometricSequenceForm.valid_filters]),
            key=lambda filter_tuple: LCOPhotometricSequenceForm.valid_filters.index(filter_tuple[0]))


class CustomLCOSpectroscopicSequenceForm(CustomLCOSequenceFormMixin, LCOSpectroscopicSequenceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['exposure_count'] = 1
        self.initial['exposure_time'] = 1800.
        self.initial['filter'] = 'slit_2.0as'
        self.initial['guider_exposure_time'] = 10.

    def layout(self):
        if settings.TARGET_PERMISSIONS_ONLY:
            groups = Row()
        else:
            groups = Row('groups')
        return Row(
            Column(
                Row('exposure_count'),
                Row('exposure_time'),
                Row('filter'),
                Row('guider_mode'),
                Row('guider_exposure_time'),
                Row('acquisition_radius'),
            ),
            Column(
                Row('max_airmass'),
                Row(PrependedText('min_lunar_distance', '>')),
                Row('site'),
                Row('proposal'),
                Row('observation_mode'),
                Row('ipp_value'),
                groups,
            ),
        )

    def observation_payload(self):
        payload = super().observation_payload()
        science_config = payload['requests'][0]['configurations'][0]

        # hardcode calibration frames into every spectrum request
        arc_config = copy.deepcopy(science_config)
        arc_config['type'] = 'ARC'
        arc_config['instrument_configs'][0]['exposure_time'] = 80.0
        arc_config['acquisition_config']['mode'] = 'OFF'
        arc_config['guiding_config']['optional'] = True
        payload['requests'][0]['configurations'].append(arc_config)

        flat_config = copy.deepcopy(arc_config)
        flat_config['type'] = 'LAMP_FLAT'
        flat_config['instrument_configs'][0]['exposure_time'] = 40.0
        payload['requests'][0]['configurations'].append(flat_config)

        return payload


class CustomLCOFacility(LCOFacility):
    observation_forms = {
        'PHOTOMETRIC_SEQUENCE': CustomLCOPhotometricSequenceForm,
        'SPECTROSCOPIC_SEQUENCE': CustomLCOSpectroscopicSequenceForm,
    }

    def save_data_products(self, observation_record, product_id=None):
        final_products = []
        products = self.data_products(observation_record.observation_id, product_id)

        for product in products:
            dp, created = DataProduct.objects.get_or_create(
                product_id=product['id'],
                target=observation_record.target,
                observation_record=observation_record,
                data_product_type='LCO',  # same as the built-in method except for this line
            )
            if created:
                product_data = requests.get(product['url']).content
                dfile = ContentFile(product_data)
                dp.data.save(product['filename'], dfile)
                dp.save()
                logger.info('Saved new dataproduct: {}'.format(dp.data))
                run_data_processor(dp)
            if settings.AUTO_THUMBNAILS:
                create_image_dataproduct(dp)
                dp.get_preview()
            final_products.append(dp)
        return final_products


class LCODataProcessor(DataProcessor):
    def process_data(self, data_product):
        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype == 'application/x-tar':  # PyRAF-based FLOYDS pipeline
            logger.info('Untarring FLOYDS file: {}'.format(data_product.data))
            with tarfile.open(fileobj=data_product.data) as targz:
                for member in targz.getmembers():
                    if member.name.endswith('_2df_ex.fits'):
                        fitsfile = targz.extractfile(member)
                        fitsname = os.path.basename(member.name)
                        dp, created = DataProduct.objects.get_or_create(
                            product_id=member.name,
                            target=data_product.target,
                            observation_record=data_product.observation_record,
                            data=ContentFile(fitsfile.read(), fitsname),
                            data_product_type='spectroscopy',
                        )
                        logger.info('Saved new dataproduct: {}'.format(dp.data))
                        run_data_processor(dp)
            data_product.delete()  # save disk space
        elif mimetype in self.FITS_MIMETYPES:
            if '-e91-1d.fits' in data_product.data.path:  # BANZAI FLOYDS pipeline
                data_product.data_product_type = 'spectroscopy'
                data_product.save()
                run_data_processor(data_product)
            elif '-e91.fits' in data_product.data.path:  # BANZAI image
                self._extract_photometry_from_banzai_catalog(data_product)
                data_product.delete()  # save disk space
        return []

    def _extract_photometry_from_banzai_catalog(self, data_product):
        hdulist = fits.open(data_product.data.path)
        hdr = hdulist['SCI'].header
        cat = hdulist['CAT'].data
        if 'mag' not in cat.names:
            logger.info(f'No calibrated BANZAI photometry in {data_product}')
            return
        target_coords = SkyCoord(data_product.target.ra, data_product.target.dec, unit='deg')
        cat_coords = SkyCoord(cat['ra'], cat['dec'], unit='deg')
        sep = cat_coords.separation(target_coords)
        imin = sep.argmin()
        if sep[imin].arcsec < 2.:
            rd, created = ReducedDatum.objects.get_or_create(
                target=data_product.target,
                # data_product=data_product,  # do not make this association so we can delete the FITS file
                data_type='photometry',
                source_name='LCO (BANZAI)',
                source_location=data_product.get_file_name(),
                timestamp=hdr.get('DATE-OBS'),
                value={
                    'filter': hdr.get('FILTER'),
                    'magnitude': cat[imin]['mag'],
                    'error': cat[imin]['magerr'],
                    'telescope': hdr.get('TELESCOP'),
                    'instrument': hdr.get('INSTRUME'),
                }
            )
            if created:
                logger.info(f'Extracted BANZAI photometry {rd} from {data_product}')
            else:
                logger.info(f'BANZAI photometry {rd} from {data_product} already extracted')
        else:
            logger.info(f'No BANZAI photometry within 2" of target in {data_product}')
