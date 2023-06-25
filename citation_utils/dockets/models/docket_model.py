import re
from datetime import date
from typing import Self

from citation_date import DOCKET_DATE_FORMAT
from citation_report.main import is_eq
from dateutil.parser import parse
from pydantic import BaseModel, ConfigDict, Field

from .docket_category import DocketCategory
from .gr_clean import gr_prefix_clean

DB_SERIAL_NUM = re.compile(r"^[a-z0-9-]+$")
"""Ideally, the docket id for the database should only be alphanumeric, lowercase with dashes."""  # noqa: E501


class Docket(BaseModel):
    """
    The Docket is the modern identifier of a Supreme Court decision.

    It is based on a `category`, a `serial id`, and a `date`.

    Field | Type | Description
    --:|:--:|:--
    `context` | optional (str) | Full text matched by the regex pattern
    `category` | optional (DocketCategory) | Whether GR, AC, etc.
    `ids` | optional (str) | The serial number of the docket category
    `docket_date` | optional (date) | The date associated with the docket

    Sample Citation | Category | Serial | Date
    :-- |:--:|:--:|:--:
    _G.R. Nos. 138570, October 10, 2000_ | GR | 74910 | October 10, 2000
    _A.M. RTJ-12-2317 (Formerly OCA I.P.I. No. 10-3378-RTJ), Jan 1, 2000_ | AM | RTJ-12-2317 |Jan 1, 2000
    _A.C. No. 10179 (Formerly CBD 11-2985), March 04, 2014_ | AC | 10179 | Mar. 4, 2014

    The Docket is often paired with a Report, which is the traditional
    identifier based on volume and page numbers.

    # TODO: need further cleaning of serial_text
    """  # noqa: E501

    model_config = ConfigDict(use_enum_values=True)
    context: str = Field(..., description="Full text matched by regex pattern.")
    category: DocketCategory = Field(..., description="e.g. General Register, etc.")
    ids: str = Field(..., description="May be comma-separated, e.g. '12, 32, and 41'")
    docket_date: date = Field(...)

    def __repr__(self) -> str:
        return f"<Docket: {self.category} {self.serial_text}, {self.formatted_date}>"

    def __str__(self) -> str:
        if self.serial_text:
            return f"{self.category} No. {self.serial_text.upper()}, {self.formatted_date}"  # noqa: E501
        return "No proper string detected."

    def __eq__(self, other: Self) -> bool:
        opt_1 = is_eq(self.category.name, other.category.name)
        opt_2 = is_eq(self.first_id, other.first_id)
        opt_3 = is_eq(self.docket_date.isoformat(), other.docket_date.isoformat())
        return all([opt_1, opt_2, opt_3])

    @property
    def slug(self):
        return "-".join(
            [self.category.name, self.serial_text, self.docket_date.isoformat()]
        )

    @property
    def serial_text(self) -> str:
        """From raw `ids`, get the `cleaned_ids`, and of these `cleaned_ids`,
            extract the `@first_id` found to deal with compound ids, e.g.
            ids separated by 'and' and ','

        Returns:
            str: Singular text identifier
        """
        if x := self.first_id or self.ids:
            if adjust := gr_prefix_clean(x):
                return adjust
        return x

    @property
    def first_id(self) -> str:
        """Get first bit from list of separated ids, when possible.

        Returns:
            str: First id found
        """

        def first_exists(char: str, text: str):
            """If a `char` exists in the `text`, split on this value."""
            return text.split(char)[0] if char in text else None

        for char in ["/", ",", ";", " and ", " AND ", "&"]:
            if res := first_exists(char, self.ids):
                return res
        return self.ids

    @property
    def formatted_date(self) -> str | None:
        if self.docket_date:
            return self.docket_date.strftime(DOCKET_DATE_FORMAT)
        return None

    @classmethod
    def from_data(cls, data: dict):
        """Presumes data with keys: `cat`, `num`, and `date`"""
        cat, num, date = data.get("cat"), data.get("num"), data.get("date")
        if not cat or not num or not date:
            raise Exception(f"Missing field for construction from {data=}")
        return cls(
            context="",
            category=DocketCategory[cat.upper()],
            ids=num,
            docket_date=parse(date).date(),
        )

    @classmethod
    def check_serial_num(cls, text: str) -> bool:
        """If a serial number exists, ensure it meets criteria prior to row creation."""
        if DB_SERIAL_NUM.search(text.lower()):
            return True
        return False
