"""Native, offline deck coordinates from the installed CubOS package."""
import json
import sys
import yaml
from cubos.deck import load_deck_from_yaml, resolve_load_names

path=sys.argv[1]
raw=resolve_load_names(yaml.safe_load(open(path)))
deck=load_deck_from_yaml(path)
items=[]
for key,labware in deck.labware.items():
    native_positions=labware.iter_positions()
    entries=native_positions.items() if hasattr(native_positions,'items') else native_positions
    positions={name:{'x':point.x,'y':point.y,'z':point.z} for name,point in entries}
    point=labware.get_initial_position() if hasattr(labware,'get_initial_position') else None
    items.append({'key':key,'config':raw['labware'].get(key,{}),'positions':{n:p for n,p in positions.items() if n!='location'},'location':{'x':point.x,'y':point.y,'z':point.z} if point else None})
print(json.dumps({'labware':items}))
