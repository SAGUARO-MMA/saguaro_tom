from django.conf import settings
from healpix_alchemy.types import Point
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, Session
from tom_nonlocalizedevents.healpix_utils import sa_engine, SaSkymapTile
from tom_surveys.models import SurveyField
from .models import SurveyFieldCredibleRegion
import json
import logging

logger = logging.getLogger(__name__)

CREDIBLE_REGION_PROBABILITIES = sorted(json.loads(settings.CREDIBLE_REGION_PROBABILITIES), reverse=True)

Base = declarative_base()


class SaSurveyField(Base):
    __tablename__ = 'tom_surveys_surveyfield'
    name = sa.Column(sa.String, primary_key=True)
    healpix = sa.Column(Point)


def update_all_credible_region_percents_for_survey_fields(eventlocalization):
    """
    This function creates a credible region linkage for each of the survey fields in the event localization specified
    """
    with Session(sa_engine) as session:

        cum_prob = sa.func.sum(
            SaSkymapTile.probdensity * SaSkymapTile.tile.area
        ).over(
            order_by=SaSkymapTile.probdensity.desc()
        ).label(
            'cum_prob'
        )

        subquery = sa.select(
            SaSkymapTile.probdensity,
            cum_prob
        ).filter(
            SaSkymapTile.localization_id == eventlocalization.id
        ).subquery()

        for prob in CREDIBLE_REGION_PROBABILITIES:
            min_probdensity = sa.select(
                sa.func.min(subquery.columns.probdensity)
            ).filter(
                subquery.columns.cum_prob <= prob
            ).scalar_subquery()

            query = sa.select(
                SaSurveyField.name
            ).filter(
                SaSkymapTile.localization_id == eventlocalization.id,
                SaSkymapTile.tile.contains(SaSurveyField.healpix),
                SaSkymapTile.probdensity >= min_probdensity
            )

            results = session.execute(query)

            for sa_survey_field in results:
                SurveyFieldCredibleRegion.objects.update_or_create(
                    survey_field = SurveyField.objects.get(name=sa_survey_field[0]),
                    localization=eventlocalization,
                    defaults={
                        'smallest_percent': int(prob * 100.0)
                    }
                )
    logger.info('Updated credible regions for survey fields')
