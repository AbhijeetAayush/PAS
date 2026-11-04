"""Links the pipeline is allowed to pull.

Add a district nagar-roll page here. Ward PDF links are read from the page.
Gram panchayat rolls come from the SEC url below. Prakhand ids must match the
ids the SEC block API returns for that district.
"""

from __future__ import annotations

SEC_VOTER_ROLL_URL = "https://sec25.bihar.gov.in/sec_new/Panchayat/VoterRoll"

# Changing this string starts a new gram-panchayat download. The old rows stay.
GRAM_PUBLICATION = "sec-panchayat-roll"

NAGAR_ROLLS: list[dict] = [
    {
        "publication": "2022-final-phase-2",
        "district_id": "22",
        "district_name": "भागलपुर",
        "page_url": "https://bhagalpur.nic.in/nagar-parisad-final-prakashan-second-phase-2022/",
        "bodies": [
            {
                "id": "akbarnagar",
                "name": "Akbarnagar",
                "name_hi": "नगर पंचायत, अकबरनगर",
                "prakhand_id": "15",
                "prakhand_name": "सुलतानगंज",
            },
            {
                "id": "naugachhia",
                "name": "Naugachhia",
                "name_hi": "नगर पंचायत, नौगछिया",
                "prakhand_id": "4",
                "prakhand_name": "नवगछिया",
            },
            {
                "id": "pirpainti",
                "name": "Pirpainti",
                "name_hi": "नगर पंचायत, पीरपैंती",
                "prakhand_id": "9",
                "prakhand_name": "पीरपैंती",
            },
            {
                "id": "sultanganj",
                "name": "Sultanganj",
                "name_hi": "नगर पंचायत, सुलतानगंज",
                "prakhand_id": "15",
                "prakhand_name": "सुलतानगंज",
            },
        ],
    },
]
