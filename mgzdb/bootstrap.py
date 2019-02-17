"""Bootstrap MGZ DB."""
import os
import json
import pkg_resources

from mgzdb import schema


def get_metadata(filename):
    """Get metadata file path."""
    return pkg_resources.resource_filename('mgzdb', os.path.join('metadata', filename))


def bootstrap(session, engine):
    """Bootstrap."""
    schema.Dataset.__table__.drop(engine, checkfirst=True)
    schema.Civilization.__table__.drop(engine, checkfirst=True)
    schema.CivilizationBonus.__table__.drop(engine, checkfirst=True)
    schema.Dataset.__table__.create(engine)
    schema.Civilization.__table__.create(engine)
    schema.CivilizationBonus.__table__.create(engine)
    for filename in pkg_resources.resource_listdir('mgzdb', 'metadata'):
        dataset_id = filename.split('.')[0]
        data = json.loads(open(get_metadata(filename), 'r').read())
        add_dataset(session, dataset_id, data)


def add_dataset(session, dataset_id, data):
    """Add a specific dataset metadata."""
    dataset = schema.Dataset(
        id=int(dataset_id),
        name=data['dataset']['name']
    )
    session.add(dataset)
    session.commit()

    for civilization_id, info in data['civilizations'].items():
        civilization = schema.Civilization(
            id=civilization_id,
            dataset=dataset,
            name=info['name']
        )
        session.add(civilization)
        for bonus in info['description']['bonuses']:
            session.add(schema.CivilizationBonus(
                civilization_id=civilization_id,
                dataset_id=dataset_id,
                type='civ',
                description=bonus
            ))
        session.add(schema.CivilizationBonus(
            civilization_id=civilization_id,
            dataset_id=dataset_id,
            type='team',
            description=info['description']['team_bonus']
        ))
        session.commit()
