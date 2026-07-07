import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class LetterNumberSymbolValidator:
    """Password must contain at least one letter, one number, and one symbol."""

    def validate(self, password, user=None):
        has_letter = re.search(r'[A-Za-z]', password or '')
        has_number = re.search(r'\d', password or '')
        has_symbol = re.search(r'[^A-Za-z0-9]', password or '')
        if not (has_letter and has_number and has_symbol):
            raise ValidationError(
                _('Password must contain at least one letter, one number, and one symbol.'),
                code='password_missing_letter_number_symbol',
            )

    def get_help_text(self):
        return _('Your password must contain at least one letter, one number, and one symbol.')
