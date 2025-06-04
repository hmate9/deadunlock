from __future__ import annotations

"""Hero enumeration and helper lookups."""

from enum import Enum


class HeroIds(Enum):
    Infernus = 1
    Seven = 2
    Vindicta = 3
    LadyGeist = 4
    Abrams = 6
    Wraith = 7
    McGinnis = 8
    Paradox = 10
    Dynamo = 11
    Kelvin = 12
    Haze = 13
    Holliday = 14
    Bebop = 15
    Calico = 16
    GreyTalon = 17
    MoAndKrill = 18
    Shiv = 19
    Ivy = 20
    Warden = 25
    Yamato = 27
    Lash = 31
    Viscous = 35
    Wrecker = 48
    Pocket = 50
    Mirage = 52
    Fathom = 53
    Dummy = 55
    Viper = 58
    Magician = 60
    Trapper = 61
    Raven = 62


_HEAD_BONES = {
    HeroIds.Abrams: 7,
    HeroIds.Bebop: 6,
    HeroIds.Dynamo: 23,
    HeroIds.GreyTalon: 17,
    HeroIds.Haze: 13,
    HeroIds.Infernus: 30,
    HeroIds.Ivy: 13,
    HeroIds.Kelvin: 12,
    HeroIds.LadyGeist: 11,
    HeroIds.Lash: 12,
    HeroIds.McGinnis: 38,
    HeroIds.MoAndKrill: 7,
    HeroIds.Paradox: 8,
    HeroIds.Pocket: 13,
    HeroIds.Seven: 14,
    HeroIds.Shiv: 13,
    HeroIds.Vindicta: 7,
    HeroIds.Viscous: 7,
    HeroIds.Warden: 11,
    HeroIds.Wraith: 7,
    HeroIds.Yamato: 34,
    HeroIds.Mirage: 8,
    HeroIds.Calico: 13,
    HeroIds.Fathom: 13,
    HeroIds.Holliday: 13,
    HeroIds.Magician: 7,
    HeroIds.Raven: 7,
    HeroIds.Trapper: 44,
    HeroIds.Viper: 13,
    HeroIds.Wrecker: 8,
}

_BODY_BONES = {
    HeroIds.Abrams: 4,
    HeroIds.Bebop: 2,
    HeroIds.Dynamo: 18,
    HeroIds.GreyTalon: 10,
    HeroIds.Haze: 9,
    HeroIds.Infernus: 11,
    HeroIds.Ivy: 9,
    HeroIds.Kelvin: 9,
    HeroIds.LadyGeist: 8,
    HeroIds.Lash: 9,
    HeroIds.McGinnis: 35,
    HeroIds.MoAndKrill: 3,
    HeroIds.Paradox: 5,
    HeroIds.Pocket: 10,
    HeroIds.Seven: 10,
    HeroIds.Shiv: 9,
    HeroIds.Vindicta: 4,
    HeroIds.Viscous: 4,
    HeroIds.Warden: 8,
    HeroIds.Wraith: 5,
    HeroIds.Yamato: 18,
    HeroIds.Mirage: 6,
    HeroIds.Calico: 10,
    HeroIds.Fathom: 10,
    HeroIds.Holliday: 10,
    HeroIds.Magician: 10,
    HeroIds.Raven: 10,
    HeroIds.Trapper: 10,
    HeroIds.Viper: 10,
    HeroIds.Wrecker: 6,
}


def get_head_bone_index(hero_id: HeroIds) -> int | None:
    """Return the bone index of the hero's head or ``None`` if unknown."""
    return _HEAD_BONES.get(hero_id)


def get_body_bone_index(hero_id: HeroIds) -> int | None:
    """Return the bone index of the hero's body or ``None`` if unknown."""
    return _BODY_BONES.get(hero_id)
