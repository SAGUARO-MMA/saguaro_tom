from django.db import models
from django.contrib.auth.models import User
from tom_targets.models import Target, TargetList
from tom_nonlocalizedevents.models import EventLocalization
from tom_surveys.models import SurveyField, SurveyObservationRecord


class Candidate(models.Model):
    candidatenumber = models.IntegerField(null=True)
    elongation = models.FloatField(null=True)
    ra = models.FloatField(null=True)
    dec = models.FloatField(null=True)
    fwhm = models.FloatField(null=True)
    snr = models.FloatField(null=True)
    mag = models.FloatField(null=True)
    magerr = models.FloatField(null=True)
    classification = models.IntegerField(null=True)
    cx = models.FloatField(null=True)
    cy = models.FloatField(null=True)
    cz = models.FloatField(null=True)
    target = models.ForeignKey(Target, null=True, on_delete=models.SET_NULL, db_column='targetid')
    mlscore = models.FloatField(null=True)
    mlscore_real = models.FloatField(null=True)
    mlscore_bogus = models.FloatField(null=True)
    observation_record = models.ForeignKey(SurveyObservationRecord, null=True, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'candidates'

class DecamCandidate(models.Model):
    """
    DECam candidates with all metadata and thumbnail images.
    This is a standalone table separate from the CSS candidates table,
    containing all information needed to vet and display DECam transients.
    """
    # Foreign Keys - matching the pattern from Candidate model
    target = models.ForeignKey(
        Target, 
        null=True, 
        on_delete=models.SET_NULL, 
        related_name='decam_candidates',
    )
    observation_record = models.ForeignKey(
        SurveyObservationRecord, 
        null=True, 
        on_delete=models.SET_NULL,
        related_name='decam_candidates'
    )
    
    # Candidate identification and position (from Candidate model)
    candidatenumber = models.IntegerField(null=True)
    ra = models.FloatField(null=True)
    dec = models.FloatField(null=True)
    
    # Source morphology (from Candidate model)
    elongation = models.FloatField(null=True)
    fwhm = models.FloatField(null=True)
    
    # Basic photometry from detection (from Candidate model)
    snr = models.FloatField(null=True)
    mag = models.FloatField(null=True)
    magerr = models.FloatField(null=True)
    
    # Cartesian coordinates for cone searches (from Candidate model)
    cx = models.FloatField(null=True)
    cy = models.FloatField(null=True)
    cz = models.FloatField(null=True)
    
    # Classification (from Candidate model)
    classification = models.IntegerField(null=True)
    
    # Machine learning scores (from Candidate model)
    mlscore = models.FloatField(null=True)
    mlscore_real = models.FloatField(null=True)
    mlscore_bogus = models.FloatField(null=True)
    
    # Observation metadata (from DecamThumbnail)
    mjd_obs = models.FloatField(null=True)
    filter_name = models.CharField(max_length=8, null=True)
    science_name = models.CharField(max_length=128, null=True)
    
    # Thumbnail images as binary PNG (from DecamThumbnail)
    thumb_template = models.BinaryField(null=True)
    thumb_science = models.BinaryField(null=True)
    thumb_difference = models.BinaryField(null=True)
    
    # DECam forced photometry (from DecamThumbnail)
    cnnscore = models.FloatField(null=True)
    snr_fphot = models.FloatField(null=True)
    mag_fphot = models.FloatField(null=True)
    magerr_fphot = models.FloatField(null=True)
    lim_mag5 = models.FloatField(null=True)
    status_fphot = models.CharField(max_length=1, null=True)
    
    # Classification flags (from DecamThumbnail)
    in_gaia = models.CharField(max_length=32, null=True)
    desi_bgs = models.CharField(max_length=32, null=True)
    desi_bgs_agn = models.CharField(max_length=32, null=True)
    
    # Metadata (from DecamThumbnail)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'decam_candidates'
        ordering = ['-mjd_obs']

    def __str__(self):
        target_name = self.target.name if self.target else "Unknown"
        return f"DECam {target_name} @ MJD {self.mjd_obs:.2f}" if self.mjd_obs else f"DECam {target_name}"
    
    @property
    def observation_date(self):
        """Return observation date in YYYY-MM-DD format from MJD"""
        if self.mjd_obs:
            from astropy.time import Time
            t = Time(self.mjd_obs, format='mjd')
            return t.datetime.strftime('%Y-%m-%d')
        return None


class SurveyFieldCredibleRegion(models.Model):
    localization = models.ForeignKey(EventLocalization, related_name='surveyfieldcredibleregions', on_delete=models.CASCADE)
    survey_field = models.ForeignKey(SurveyField, related_name='credibleregions', on_delete=models.CASCADE)
    observation_record = models.ForeignKey(SurveyObservationRecord, null=True, on_delete=models.SET_NULL)

    smallest_percent = models.IntegerField(
        default=100,
        help_text='Smallest percent credible region this field falls into for this localization.'
    )
    probability_contained = models.FloatField(null=True)
    group = models.IntegerField(null=True)
    rank_in_group = models.IntegerField(null=True)
    scheduled_start = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['localization', 'survey_field'], name='unique_localization_survey_field')
        ]
        ordering = ['group', 'rank_in_group', '-probability_contained']


class CredibleRegionContour(models.Model):
    localization = models.ForeignKey(EventLocalization, related_name='credible_region_contours', on_delete=models.CASCADE)
    probability = models.FloatField()
    pixels = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['localization', 'probability'], name='unique_localization_probability')
        ]
