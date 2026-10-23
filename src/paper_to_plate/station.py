"""Fresh station configuration reads; no connect, motion or inventory writes."""
import hashlib
import time

import httpx
import yaml
from .preparation import demand

from . import store
from .config import CUBOS_URL

GANTRY_FILE = 'picus120_fast_camera_20261014.yaml'
DECK_FILE = 'cub_deck.yaml'


async def read_config(client, category, name):
    response = await client.get(CUBOS_URL+f'/api/v1/configs/{category}/{name}/raw')
    response.raise_for_status()
    text = response.json()['content']
    if not isinstance(text,str) or len(text)>300000:
        raise ValueError('Station configuration has an unsupported size or format.')
    return text


async def import_setup():
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        status = await client.get(CUBOS_URL+'/api/v1/station/status')
        status.raise_for_status()
        gantry = await read_config(client,'gantry',GANTRY_FILE)
        deck = await read_config(client,'deck',DECK_FILE)
    return store.create('setups', name='Color matching · station files', gantry_yaml=gantry,
        deck_yaml=deck, fluids_yaml='fluids: {}\n', first_tip='A1', nominal_vial_capacity_ul=5000,
        materials='User-loaded stock-holder columns: 1 red, 2 yellow, 3 blue, 4 water, 5 empty. Use row A. Actual identities, amounts, empty destination wells and fresh tips require operator confirmation.',
        station_source={'url':CUBOS_URL,'gantry_file':GANTRY_FILE,'deck_file':DECK_FILE,'fetched_at':time.time(),
            'gantry_sha256':hashlib.sha256(gantry.encode()).hexdigest(),
            'deck_sha256':hashlib.sha256(deck.encode()).hexdigest(),
            'note':'Fresh saved-file read; not proof of physical commissioning or active calibration.'})


async def verify_setup(run):
    source = run['setup_snapshot'].get('station_source')
    if not source:
        return
    if source['url'] != CUBOS_URL:
        raise ValueError('The station address changed. Import and review the setup again.')
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        for kind in ('gantry','deck'):
            text = await read_config(client,kind,source[kind+'_file'])
            if hashlib.sha256(text.encode()).hexdigest() != source[kind+'_sha256']:
                raise ValueError(f'The station {kind} file changed. Rebuild and review the experiment before running.')
        response = await client.get(CUBOS_URL+'/api/v1/station/status')
        response.raise_for_status()
        state = response.json()
        if not state.get('connected') or state.get('active_run_id') or state.get('calibration_active') or state.get('reserved'):
            raise ValueError('The station must be connected, idle and available before this handoff.')

        inventory_id = run['setup_snapshot'].get('station_fluid_state_id')
        if inventory_id:
            inventory_response = await client.get(CUBOS_URL+f'/api/v1/fluid-states/{inventory_id}')
            inventory_response.raise_for_status()
            inventory = inventory_response.json()
            if inventory.get('pending_operation_count') or inventory.get('reconciliation_required_count'):
                raise ValueError('CubOS inventory has unresolved operations. Reconcile before running.')
            containers = {c['labware_key']+('.'+c['location_id'] if c['location_id'] else ''): c for c in inventory['containers']}
            required, touched = demand(run['protocol_yaml'])
            planned = yaml.safe_load(run['setup_snapshot']['fluids_yaml'])['fluids']
            for position in touched:
                current = containers.get(position)
                if current is None:
                    raise ValueError(f'{position}: missing from live CubOS inventory.')
                if position in required:
                    if current['current_volume_ul'] < planned[position]['volume_ul']:
                        raise ValueError(f'{position}: live CubOS stock is below the confirmed loading amount.')
                    if set(current['composition']) != set(planned[position]['composition']):
                        raise ValueError(f'{position}: live stock identity differs from the preparation sheet.')
                elif current['current_volume_ul'] != 0:
                    raise ValueError(f'{position}: destination is occupied in live CubOS inventory.')
            tips_response = await client.get(CUBOS_URL+f'/api/v1/fluid-states/{inventory_id}/tips')
            tips_response.raise_for_status()
            tips = {(t['rack_key'],t['slot_id']): t['status'] for t in tips_response.json()['containers']}
            for command in yaml.safe_load(run['protocol_yaml'])['protocol']:
                if 'pick_up_tip' in command:
                    args = command['pick_up_tip']
                    position = args['position']
                    rack, slot = position.rsplit('.',1)
                    if tips.get((rack,slot)) != 'available':
                        raise ValueError(f'{position}: tip is not available in live CubOS inventory.')
