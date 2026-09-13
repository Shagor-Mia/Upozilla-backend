"""Bangladesh's 8 divisions and 64 districts (stable since Mymensingh became the
8th division in 2015; district boundaries unchanged since 1984).

Upazila/Union levels are NOT included here — Section 4 of the plan says those
get added per-upazila as each one launches, not as a nationwide bulk seed.
"""

DIVISIONS_WITH_DISTRICTS: dict[str, list[str]] = {
    "Dhaka": [
        "Dhaka", "Faridpur", "Gazipur", "Gopalganj", "Kishoreganj", "Madaripur",
        "Manikganj", "Munshiganj", "Narayanganj", "Narsingdi", "Rajbari",
        "Shariatpur", "Tangail",
    ],
    "Chattogram": [
        "Bandarban", "Brahmanbaria", "Chandpur", "Chattogram", "Cox's Bazar",
        "Cumilla", "Feni", "Khagrachhari", "Lakshmipur", "Noakhali", "Rangamati",
    ],
    "Rajshahi": [
        "Bogura", "Joypurhat", "Naogaon", "Natore", "Chapainawabganj", "Pabna",
        "Rajshahi", "Sirajganj",
    ],
    "Khulna": [
        "Bagerhat", "Chuadanga", "Jashore", "Jhenaidah", "Khulna", "Kushtia",
        "Magura", "Meherpur", "Narail", "Satkhira",
    ],
    "Barishal": [
        "Barguna", "Barishal", "Bhola", "Jhalokati", "Patuakhali", "Pirojpur",
    ],
    "Sylhet": [
        "Habiganj", "Moulvibazar", "Sunamganj", "Sylhet",
    ],
    "Rangpur": [
        "Dinajpur", "Gaibandha", "Kurigram", "Lalmonirhat", "Nilphamari",
        "Panchagarh", "Rangpur", "Thakurgaon",
    ],
    "Mymensingh": [
        "Jamalpur", "Mymensingh", "Netrokona", "Sherpur",
    ],
}
