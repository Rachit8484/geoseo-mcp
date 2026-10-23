"""Google structured-data requirements, encoded as a static table.

Source: Google Search Central structured-data feature guides
(https://developers.google.com/search/docs/appearance/structured-data/search-gallery),
checked October 2026. Only properties Google documents are listed; schema.org
allows far more.

Path syntax used by the linter:
    ``a.b``    nested property
    ``a[].b``  every element of list ``a`` must have ``b``
``any_of`` lists groups where at least one property must be present.
``nested`` maps a property to the rule set its value(s) should satisfy.
"""

from __future__ import annotations

from typing import Any

DOCS = "https://developers.google.com/search/docs/appearance/structured-data/"

RULES: dict[str, dict[str, Any]] = {
    "Article": {
        "doc": DOCS + "article",
        "required": [],
        "recommended": ["headline", "image", "datePublished", "dateModified",
                        "author", "author.name"],
        "note": "Google has no required Article properties; missing recommended "
                "ones (especially author and dates) weaken eligibility.",
    },
    "Product": {
        "doc": DOCS + "product-snippet",
        "required": ["name"],
        "any_of": [["review", "aggregateRating", "offers"]],
        "recommended": ["image", "description", "brand.name", "sku",
                        "aggregateRating", "review", "offers"],
        "nested": {"offers": "Offer", "aggregateRating": "AggregateRating",
                   "review": "NestedReview"},
        "note": "Merchant listings additionally require image and offers "
                "(with price and priceCurrency).",
    },
    "Offer": {
        "doc": DOCS + "product-snippet#offer-details",
        "required": ["price"],
        "recommended": ["priceCurrency", "availability", "priceValidUntil"],
    },
    "AggregateOffer": {
        "doc": DOCS + "product-snippet#aggregate-offer",
        "required": ["lowPrice", "priceCurrency"],
        "recommended": ["highPrice", "offerCount"],
    },
    "AggregateRating": {
        "doc": DOCS + "review-snippet#aggregated-rating-type-definition",
        "required": ["ratingValue"],
        "any_of": [["ratingCount", "reviewCount"]],
        "recommended": ["bestRating", "worstRating"],
    },
    "NestedReview": {
        "doc": DOCS + "review-snippet#review-properties",
        "required": ["author", "reviewRating", "reviewRating.ratingValue"],
        "recommended": ["datePublished", "reviewRating.bestRating"],
    },
    "Review": {
        "doc": DOCS + "review-snippet#review-properties",
        "required": ["author", "itemReviewed", "itemReviewed.name", "reviewRating",
                     "reviewRating.ratingValue"],
        "recommended": ["datePublished", "reviewRating.bestRating",
                        "reviewRating.worstRating"],
    },
    "Recipe": {
        "doc": DOCS + "recipe",
        "required": ["name", "image"],
        "recommended": ["recipeIngredient", "recipeInstructions", "author", "datePublished",
                        "description", "prepTime", "cookTime", "totalTime", "recipeYield",
                        "recipeCategory", "recipeCuisine", "keywords",
                        "nutrition.calories", "aggregateRating", "video"],
        "nested": {"aggregateRating": "AggregateRating"},
    },
    "LocalBusiness": {
        "doc": DOCS + "local-business",
        "required": ["name", "address"],
        "recommended": ["telephone", "url", "geo.latitude", "geo.longitude",
                        "openingHoursSpecification", "priceRange", "image"],
        "nested": {"aggregateRating": "AggregateRating"},
    },
    "BreadcrumbList": {
        "doc": DOCS + "breadcrumb",
        "required": ["itemListElement", "itemListElement[].position",
                     "itemListElement[].name", "itemListElement[].item"],
        "recommended": [],
        "note": "item may be omitted on the last breadcrumb.",
    },
    "Event": {
        "doc": DOCS + "event",
        "required": ["name", "startDate", "location", "location.address"],
        "recommended": ["description", "endDate", "eventStatus", "image", "location.name",
                        "offers", "organizer", "performer"],
        "nested": {"offers": "Offer"},
    },
    "VideoObject": {
        "doc": DOCS + "video",
        "required": ["name", "thumbnailUrl", "uploadDate"],
        "recommended": ["description", "contentUrl", "embedUrl", "duration"],
    },
    "SoftwareApplication": {
        "doc": DOCS + "software-app",
        "required": ["name", "offers.price"],
        "any_of": [["aggregateRating", "review"]],
        "recommended": ["applicationCategory", "operatingSystem"],
        "nested": {"aggregateRating": "AggregateRating", "review": "NestedReview"},
    },
    "JobPosting": {
        "doc": DOCS + "job-posting",
        "required": ["title", "description", "datePosted", "hiringOrganization",
                     "jobLocation"],
        "recommended": ["validThrough", "employmentType", "baseSalary", "identifier",
                        "directApply"],
        "note": "Fully remote jobs can use jobLocationType=TELECOMMUTE with "
                "applicantLocationRequirements instead of jobLocation.",
    },
    "QAPage": {
        "doc": DOCS + "qapage",
        "required": ["mainEntity", "mainEntity.name", "mainEntity.answerCount"],
        "any_of": [["mainEntity.acceptedAnswer", "mainEntity.suggestedAnswer"]],
        "recommended": ["mainEntity.author", "mainEntity.datePublished"],
    },
    "FAQPage": {
        "doc": "https://schema.org/FAQPage",
        "required": ["mainEntity", "mainEntity[].name", "mainEntity[].acceptedAnswer",
                     "mainEntity[].acceptedAnswer.text"],
        "recommended": [],
        "note": "Google no longer documents FAQ rich results; the markup can still "
                "help other engines and LLMs parse Q&A content.",
    },
    "HowTo": {
        "doc": "https://schema.org/HowTo",
        "required": ["name", "step"],
        "recommended": ["image", "totalTime", "supply", "tool"],
        "note": "Google retired HowTo rich results; validated against schema.org only.",
    },
    "Organization": {
        "doc": DOCS + "organization",
        "required": [],
        "recommended": ["name", "url", "logo", "sameAs", "description", "address",
                        "contactPoint"],
    },
}

# Subtypes that should be checked with a parent's rules.
ALIASES: dict[str, str] = {
    "NewsArticle": "Article",
    "BlogPosting": "Article",
    "TechArticle": "Article",
    "ScholarlyArticle": "Article",
    "Report": "Article",
    "MobileApplication": "SoftwareApplication",
    "WebApplication": "SoftwareApplication",
    "VideoGame": "SoftwareApplication",
    "ProductGroup": "Product",
    "Corporation": "Organization",
    "NGO": "Organization",
    "OnlineStore": "Organization",
    "OnlineBusiness": "Organization",
    "EducationalOrganization": "Organization",
    "MedicalOrganization": "Organization",
    "MusicEvent": "Event",
    "SportsEvent": "Event",
    "BusinessEvent": "Event",
    "EducationEvent": "Event",
    "Festival": "Event",
    "TheaterEvent": "Event",
    "ComedyEvent": "Event",
    "ExhibitionEvent": "Event",
}

# Common schema.org LocalBusiness subtypes (non-exhaustive; the linter also
# treats any type ending in "Business" or "Store" as a LocalBusiness).
LOCAL_BUSINESS_SUBTYPES = {
    "Restaurant", "CafeOrCoffeeShop", "Bakery", "BarOrPub", "FastFoodRestaurant",
    "Dentist", "Physician", "MedicalClinic", "Hospital", "Pharmacy", "Optician",
    "Attorney", "LegalService", "Notary", "AccountingService", "FinancialService",
    "BankOrCreditUnion", "InsuranceAgency", "RealEstateAgent", "TravelAgency",
    "HairSalon", "BeautySalon", "DaySpa", "NailSalon", "HealthClub", "ExerciseGym",
    "AutoRepair", "AutoDealer", "Plumber", "Electrician", "HVACBusiness",
    "RoofingContractor", "Locksmith", "MovingCompany", "HomeAndConstructionBusiness",
    "Hotel", "Motel", "LodgingBusiness", "ChildCare", "Library", "VeterinaryCare",
    "FoodEstablishment", "EntertainmentBusiness", "ProfessionalService",
}


def resolve(type_name: str) -> str | None:
    """Map a schema.org type to the rule set that applies, if any."""
    if type_name in RULES:
        return type_name
    if type_name in ALIASES:
        return ALIASES[type_name]
    if (
        type_name in LOCAL_BUSINESS_SUBTYPES
        or type_name.endswith(("Business", "Store"))
    ):
        return "LocalBusiness"
    return None
