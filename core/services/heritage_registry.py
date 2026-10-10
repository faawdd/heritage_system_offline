"""Keep imported registration forms connected to the operational heritage registry."""
import json

from core.models import HeritageSite


def sync_registration(heritage, *, sync_boundaries=True, overwrite_boundaries=True, site_model=HeritageSite):
    site = site_model.objects.filter(registration_id=heritage.pk).first()
    if site is None:
        site = site_model.objects.filter(sip_code=heritage.survey_code).first()
    if site is not None and site.registration_id not in (None, heritage.pk):
        raise ValueError(f'四普编号 {heritage.survey_code} 已关联其他文物档案')
    created = site is None
    if created:
        site = site_model()
    site.registration_id = heritage.pk
    for target, source in (
        ('sip_code', 'survey_code'), ('name', 'name'), ('category', 'category'),
        ('level', 'protection_level'), ('address', 'address'), ('manager', 'manager'),
        ('description', 'description'), ('longitude', 'longitude'), ('latitude', 'latitude'),
    ):
        setattr(site, target, getattr(heritage, source))
    site.category = 'GYZ' if heritage.category == 'GWZ' else heritage.category
    for name in ('body_boundary', 'protection_zone', 'control_zone'):
        rings = getattr(heritage, name)
        if created or (sync_boundaries and (overwrite_boundaries or not getattr(site, name))):
            setattr(site, name, json.dumps(rings, ensure_ascii=False) if rings else '')
    site.save()
    return site, created


def sync_site_to_registration(site):
    if not site.registration_id:
        return
    heritage = site.registration
    for target, source in (
        ('survey_code', 'sip_code'), ('name', 'name'), ('protection_level', 'level'),
        ('address', 'address'), ('manager', 'manager'), ('description', 'description'),
        ('longitude', 'longitude'), ('latitude', 'latitude'),
    ):
        setattr(heritage, target, getattr(site, source))
    heritage.category = 'GWZ' if site.category == 'GYZ' else site.category
    for name in ('body_boundary', 'protection_zone', 'control_zone'):
        setattr(heritage, name, json.loads(getattr(site, name)) if getattr(site, name) else [])
    heritage.save()
