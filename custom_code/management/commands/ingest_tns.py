from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from trove_targets.models import Target
from custom_code.healpix_utils import create_candidates_from_targets
from custom_code.alertstream_handlers import pick_slack_channel, send_slack, vet_or_post_error
from custom_code.templatetags.skymap_extras import get_preferred_localization
from tom_nonlocalizedevents.models import NonLocalizedEvent
from datetime import datetime, timedelta, timezone
from custom_code.templatetags.target_extras import split_name
from slack_sdk import WebClient
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)
new_format = logging.Formatter('[%(asctime)s] %(levelname)s : s%(message)s')
for handler in logger.handlers:
    handler.setFormatter(new_format)

slack_tns = WebClient(settings.SLACK_TOKEN_TNS)
slack_tns50 = WebClient(settings.SLACK_TOKEN_TNS50)
slack_ep = WebClient(settings.SLACK_TOKEN_EP)


def get_active_nonlocalizedevents(t0=None, lookback_days=3., test=False):
    """
    Returns a queryset containing "active" NonLocalizedEvents, significant events that happened less than
    `lookback_days` before `t0` and have not been retracted. Use `test=True` to query mock events instead of real ones.
    """
    if t0 is None:
        t0 = datetime.now(tz=timezone.utc)
    lookback_window_nle = (t0 - timedelta(days=lookback_days)).isoformat()
    active_nles = NonLocalizedEvent.objects.filter(sequences__details__time__gte=lookback_window_nle, state='ACTIVE')
    active_nles = active_nles.exclude(sequences__details__significant=False)
    if test:
        active_nles = active_nles.filter(event_id__startswith='MS')
    else:
        active_nles = active_nles.exclude(event_id__startswith='MS')
    return active_nles.distinct()

class Command(BaseCommand):

    help = 'Updates, merges, and adds targets from the tns_q3c table (maintained outside the TOM Toolkit)'

    def add_arguments(self, parser):
        parser.add_argument('--lookback-days-nle', help='Nonlocalized events are considered active for this many days',
                            type=float, default=7.)
        parser.add_argument('--lookback-days-obs', help='Associate transients whose first detection was within this '
                                                        'many days of the nonlocalized event',
                            type=float, default=3.)

    def handle(self, lookback_days_nle=7., lookback_days_obs=3., **kwargs):
        
        with connection.cursor() as cursor:
             cursor.execute("""
                 --STEP 0: update coordinates and prefix of existing targets with TNS names
                 UPDATE tom_targets_basetarget AS tt
                 SET name = CONCAT(tns.name_prefix, tns.name),
                     ra = tns.ra,
                     dec = tns.declination,
                     modified = NOW()
                 FROM tns_q3c AS tns
                 WHERE REGEXP_REPLACE(tt.name, '^[^0-9]*', '') = tns.name
                   AND (q3c_dist(tt.ra, tt.dec, tns.ra, tns.declination) > 0
                        OR tt.name != CONCAT(tns.name_prefix, tns.name))
                 RETURNING tt.id;
             """)
             updated_ids = [row[0] for row in cursor.fetchall()]
             updated_targets_coords = Target.objects.filter(id__in = updated_ids)
        
        logger.info(f"Updated coordinates of {len(updated_targets_coords):d} targets to match the TNS.")

        logger.info('Crossmatching TNS with targets table. This will take several minutes.')
        with connection.cursor() as cursor:
            cursor.execute(
                """
                --STEP 1: crossmatch TNS transients with existing targets and store in tns_matches table
                CREATE TEMPORARY TABLE tns_matches AS
                SELECT target.id, target.name, t.tns_name, t.sep, t.ra, t.dec
                FROM tom_targets_basetarget AS target LEFT JOIN LATERAL (
                    SELECT CONCAT(tns.name_prefix, tns.name) AS tns_name,
                        q3c_dist(target.ra, target.dec, tns.ra, tns.declination) AS sep,
                        tns.ra,
                        tns.declination as dec
                    FROM tns_q3c AS tns
                    WHERE q3c_join(target.ra, target.dec, tns.ra, tns.declination, 2. / 3600) AND name_prefix != 'FRB'
                    ORDER BY sep, discoverydate LIMIT 1 -- if there are duplicates in the TNS, use the earlier one
                ) AS t ON true
                WHERE t.tns_name IS NOT NULL;
                
                -- the top_tns_matches table tells you the target names and coordinates we are going to adopt
                CREATE TEMPORARY TABLE top_tns_matches AS
                SELECT DISTINCT ON (tns_name) *
                FROM tns_matches
                ORDER BY tns_name, name=tns_name desc, sep; -- prefer the one that already has the TNS name, if any
                
                -- after this, the tns_matches table tells you which targets need to be merged and deleted
                DELETE FROM tns_matches
                WHERE name IN (
                    SELECT name from top_tns_matches
                );
                """
            )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                --STEP 2: update existing non-TNS targets within 2" of a TNS transient to have the TNS name and coordinates
                UPDATE tom_targets_basetarget AS tt
                SET name=tm.tns_name, ra=tm.ra, dec=tm.dec, modified=NOW()
                FROM top_tns_matches AS tm
                WHERE tt.name=tm.name AND (tm.name != tm.tns_name OR sep > 0)
                RETURNING tt.id;
                """
            )
            updated_ids = [row[0] for row in cursor.fetchall()]
            updated_targets = Target.objects.filter(id__in = updated_ids)

            
        logger.info(f"Updated {len(updated_targets):d} targets to match the TNS.")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                --STEP 3: merge any other matches into the new target
                CREATE TEMPORARY TABLE targets_to_merge AS
                SELECT tm.id AS old_id, ttm.id  AS new_id, tm.name AS old_name, ttm.name AS new_name
                FROM tns_matches as tm
                JOIN top_tns_matches AS ttm ON ttm.name=tm.tns_name;
                
                UPDATE candidates
                SET targetid=new_id
                FROM targets_to_merge
                WHERE targetid=old_id;
                
                UPDATE tom_dataproducts_dataproduct
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                
                UPDATE tom_dataproducts_reduceddatum
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                
                UPDATE tom_nonlocalizedevents_eventcandidate
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                
                UPDATE tom_observations_observationrecord
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                
                UPDATE tom_targets_targetextra
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id
                AND NOT EXISTS (
                    SELECT 1 FROM tom_targets_targetextra
                    WHERE target_id=new_id AND key=key
                );

                DELETE FROM tom_targets_targetextra
                WHERE target_id IN (SELECT old_id FROM targets_to_merge);
                
                UPDATE tom_targets_targetlist_targets
                SET basetarget_id=new_id
                FROM targets_to_merge
                WHERE basetarget_id=old_id;
                
                UPDATE tom_targets_targetname
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                """
            )

        with connection.cursor() as cursor:
             cursor.execute(
                """
                SELECT old_id FROM targets_to_merge
                """
             )
             ids_to_delete = [row[0] for row in cursor.fetchall()]

        deleted_targets = Target.objects.filter(id__in = ids_to_delete)
        deleted_targets.delete()
             
        logger.info(f"Merged {len(deleted_targets):d} targets into TNS targets.")
        for target in deleted_targets:
            logger.info(f" - deleted target {target.name} during merge")

        with connection.cursor() as cursor:
             cursor.execute(
                """
                --STEP 4: add all other unmatched TNS transients to the targets table (removing duplicate names)
                INSERT INTO tom_targets_basetarget (name, type, created, modified, permissions, ra, dec, epoch, scheme)
                SELECT CONCAT(name_prefix, name), 'SIDEREAL', NOW(), NOW(), 'PUBLIC', ra, declination, 2000, ''
                FROM tns_q3c WHERE name_prefix != 'FRB' AND name != '2023hzc' -- this is a duplicate of AT2016jlf in the TNS
                ON CONFLICT (name) DO NOTHING
                RETURNING id;
                """
             )

             new_target_ids = [row[0] for row in cursor.fetchall()]
             new_targets = Target.objects.filter(id__in = new_target_ids)
             
        logger.info(f"Added {len(new_targets):d} new targets from the TNS.")

        for targets in [new_targets, updated_targets]:
            for target in targets:
                vet_or_post_error(target, slack_tns, channel='alerts-tns')
                
        # automatically associate with nonlocalized events
        for nle in get_active_nonlocalizedevents(lookback_days=lookback_days_nle):
            seq = nle.sequences.last()
            localization = get_preferred_localization(nle)
            nle_time = datetime.strptime(seq.details['time'], '%Y-%m-%dT%H:%M:%S.%f%z')
            target_ids = []
            for targets in [new_targets, updated_targets, updated_targets_coords]:
                for target in targets:
                    first_det = target.reduceddatum_set.filter(data_type='photometry', value__magnitude__isnull=False
                                                               ).order_by('timestamp').first()
                    if first_det and nle_time < first_det.timestamp < nle_time + timedelta(days=lookback_days_obs):
                        target_ids.append(target.id)
            candidates = create_candidates_from_targets(seq, target_ids=target_ids)
            for candidate in candidates:
                credible_region = candidate.credibleregions.get(localization=localization).smallest_percent
                format_kwargs = {'nle': nle, 'target': candidate.target, 'credible_region': credible_region}
                slack_alert = ('<{target_link}|{{target.name}}> falls in the {{credible_region:d}}% '
                               'localization region of <{nle_link}|{{nle.event_id}}>')
                if nle.event_type == nle.NonLocalizedEventType.GRAVITATIONAL_WAVE:
                    send_slack(slack_alert, format_kwargs, *pick_slack_channel(seq))
                elif nle.event_type == nle.NonLocalizedEventType.UNKNOWN:
                    body = slack_alert.format(nle_link=settings.NLE_LINKS[0][0],
                                              target_link=settings.TARGET_LINKS[0][0])
                    slack_ep.chat_postMessage(channel='alerts-ep', text=body.format(**format_kwargs))
