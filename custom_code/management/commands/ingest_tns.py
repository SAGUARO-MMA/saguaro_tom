from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from tom_targets.models import Target
from ...hooks import target_post_save
import requests
import json
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = 'Updates, merges, and adds targets from the tns_q3c table (maintained outside the TOM Toolkit)'

    def handle(self, **kwargs):
        logger.info('Crossmatching TNS with targets table. This will take several minutes.')

        with connection.cursor() as cursor:
            cursor.execute(
                """
                --STEP 1: crossmatch TNS transients with existing targets and store in tns_matches table
                SELECT target.id, target.name, t.tns_name, t.sep, t.ra, t.dec INTO tns_matches
                FROM tom_targets_target AS target LEFT JOIN LATERAL (
                    SELECT CONCAT(tns.name_prefix, tns.name) AS tns_name,
                        q3c_dist(target.ra, target.dec, tns.ra, tns.declination) AS sep,
                        tns.ra,
                        tns.declination as dec
                    FROM tns_q3c AS tns
                    WHERE q3c_join(target.ra, target.dec, tns.ra, tns.declination, 2. / 3600) AND name_prefix != 'FRB'
                    ORDER BY sep, discoverydate LIMIT 1 -- if there are duplicates in the TNS, use the earlier one
                ) AS t ON true
                WHERE t.tns_name IS NOT NULL;
                
                SELECT DISTINCT ON (tns_name) * INTO top_tns_matches
                FROM tns_matches
                ORDER BY tns_name, sep, name; -- if there are duplicates in the TNS, use the earlier one
                
                DELETE FROM tns_matches
                WHERE name IN (
                    SELECT name from top_tns_matches
                );
                """
            )

        updated_targets = Target.objects.raw(
            """
            --STEP 2: update existing targets (if needed) to match closest TNS transient
            UPDATE tom_targets_target AS tt
            SET name=tm.tns_name, ra=tm.ra, dec=tm.dec, modified=NOW()
            FROM top_tns_matches AS tm
            WHERE tt.name=tm.name AND (tm.name != tm.tns_name OR sep > 0)
            RETURNING tt.*;
            """
        )
        logger.info(f"Updated {len(updated_targets):d} targets to match the TNS.")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                --STEP 3: merge any other matches into the new target
                SELECT tm.id AS old_id, ttm.id  AS new_id, tm.name AS old_name, ttm.name AS new_name
                INTO targets_to_merge
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
                WHERE target_id=old_id;
                
                UPDATE tom_targets_targetlist_targets
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                
                UPDATE tom_targets_targetname
                SET target_id=new_id
                FROM targets_to_merge
                WHERE target_id=old_id;
                """
            )

        deleted_targets = Target.objects.raw(
            """
            DELETE FROM tom_targets_target
            WHERE id IN (
                SELECT old_id FROM targets_to_merge
            )
            RETURNING *;
            """
        )
        logger.info(f"Merged {len(deleted_targets):d} targets into TNS targets.")
        for target in deleted_targets:
            logger.info(f" - deleted target {target.name} during merge")

        new_targets = Target.objects.raw(
            """
            --STEP 4: add all other unmatched TNS transients to the targets table (removing duplicate names)
            INSERT INTO tom_targets_target (name, type, created, modified, ra, dec, epoch, scheme)
            SELECT CONCAT(name_prefix, name), 'SIDEREAL', NOW(), NOW(), ra, declination, 2000, ''
            FROM tns_q3c WHERE name_prefix != 'FRB' AND name != '2023hzc' -- this is a duplicate in the TNS
            ON CONFLICT (name) DO NOTHING
            RETURNING *;
            """
        )
        logger.info(f"Added {len(new_targets):d} new targets from the TNS.")

        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE tns_matches, top_tns_matches, targets_to_merge; -- cleanup")

        for target in updated_targets:
            target_post_save(target, created=True)
        for target in new_targets:
            target_post_save(target, created=True)
            for galaxy in json.loads(target.targetextra_set.get(key='Host Galaxies').value):
                if galaxy['Dist'] <= 40.:
                    slack_alert = (f'<https://sand.as.arizona.edu/saguaro_tom/targets/{target.id}/|{target.name}> is '
                                   f'{galaxy["Offset"]:.1f}" from galaxy {galaxy["ID"]} at {galaxy["Dist"]:.1f} Mpc')
                    json_data = json.dumps({'text': slack_alert}).encode('ascii')
                    requests.post(settings.SLACK_TNS_URL, data=json_data, headers={'Content-Type': 'application/json'})
                    break
