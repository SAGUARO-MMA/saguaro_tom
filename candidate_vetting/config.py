"""
Some config variables for vetting that are used in multiple places
"""
from .vet_basic import vet_basic
from .vet_bns import vet_bns
#from .vet_kn_in_sn import vet_kn_in_sn
#from .vet_super_kn import vet_super_kn

VETTING_FORM_CHOICES = [ # these tuples are (value to save, value to show)
    ("KN", "Classical Kilonova"),
#    ("KNinSN", "Kilonova in Supernova"),
#    ("superKN", "Super-Kilonova"),
#    ("agn", "BBH and/or AGN Flare"),
    ("basic", "Basic Vetting")
]

FORM_CHOICE_FUNC_MAP = { # this should have the same keys as the VETTING_FORM_CHOICES variable!
    "KN":vet_bns,
#    "KNinSN":vet_kn_in_sn,
#    "superKN":vet_super_kn,
#    "agn":???,
    "basic":vet_basic
}
