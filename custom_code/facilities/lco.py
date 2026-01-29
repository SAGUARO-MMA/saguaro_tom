from tom_observations.facilities.lco import LCOFacility
from tom_dataproducts.data_processor import run_data_processor, DataProcessor
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.utils import create_image_dataproduct
from astropy.coordinates import SkyCoord
from astropy.io import fits
from django.core.files.base import ContentFile
from django.conf import settings
import requests
import mimetypes
import tarfile
import os
import logging

logger = logging.getLogger(__name__)


class CustomLCOFacility(LCOFacility):
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
