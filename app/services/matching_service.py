from app.models.donor_profile import DonorProfile
from app.models.user import User
from app.utils.blood_compatibility import can_donate_to


class MatchingService:
    @staticmethod
    def find_compatible_donors(request_blood_group, city=None, state=None, area=None, emergency_only=False):
        allowed_groups = set()
        for donor_group in ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]:
            if can_donate_to(donor_group, request_blood_group):
                allowed_groups.add(donor_group)

        query = DonorProfile.query.join(User).filter(
            User.is_active.is_(True),
            User.is_verified.is_(True),
            DonorProfile.visibility == "public",
            DonorProfile.availability == "available",
        )

        if emergency_only:
            query = query.filter(DonorProfile.emergency_available.is_(True))

        query = query.filter(DonorProfile.blood_group.in_(list(allowed_groups)))

        if city:
            query = query.filter(DonorProfile.city.ilike(f"%{city}%"))
        if state:
            query = query.filter(DonorProfile.state.ilike(f"%{state}%"))
        if area:
            query = query.filter(DonorProfile.area.ilike(f"%{area}%"))

        return query.order_by(DonorProfile.emergency_available.desc(), DonorProfile.updated_at.desc()).all()
