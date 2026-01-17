from django.forms import (
    Form,
    ChoiceField,
    RadioSelect
)

class VettingChoiceForm(Form):
    choices = [ # these tuples are (value to save, value to show)
        ("KN", "Classical Kilonova"),
        ("KN-in-SN", "Kilonova in Supernova"),
        ("superKN", "Super-Kilonova"),
        ("agn", "BBH and/or AGN Flare"),
        ("basic", "Basic Vetting")
    ]
    picked = ChoiceField(
        choices = choices,
        widget = RadioSelect()
    )
