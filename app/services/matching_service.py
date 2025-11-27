"""
AI-powered matching service for suppliers and RFQs
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.orm import RFQ, Company, User, UserRole, RFQStatus
from app.services.llm_service import llm_service


class MatchingService:
    """Service for intelligent RFQ-Supplier matching"""

    async def get_matched_rfqs_for_supplier(
        self, 
        db: AsyncSession, 
        supplier_user: User, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get RFQs matched to supplier's capabilities using AI.
        """
        if supplier_user.role != UserRole.SUPPLIER:
            return []

        # Get open RFQs (excluding supplier's own company)
        result = await db.execute(
            select(RFQ, Company.name)
            .join(Company, RFQ.buyer_company_id == Company.id)
            .where(and_(
                RFQ.status == RFQStatus.OPEN,
                RFQ.buyer_company_id != supplier_user.company_id,
                RFQ.deadline > func.now()
            ))
            .order_by(RFQ.created_at.desc())
            .limit(limit * 2)  # Get more to filter
        )

        rfqs_with_companies = result.fetchall()
        
        # AI-powered matching
        matched_rfqs = []
        supplier_profile = await self._get_supplier_profile(db, supplier_user)
        
        for rfq, buyer_company_name in rfqs_with_companies:
            match_score = await self._calculate_match_score(rfq, supplier_profile)
            
            if match_score > 0.3:  # Threshold for relevance
                matched_rfqs.append({
                    "rfq": rfq,
                    "buyer_company": buyer_company_name,
                    "match_score": match_score,
                    "match_reasons": await self._get_match_reasons(rfq, supplier_profile)
                })
        
        # Sort by match score and return top matches
        matched_rfqs.sort(key=lambda x: x["match_score"], reverse=True)
        return matched_rfqs[:limit]

    async def get_recommended_suppliers_for_rfq(
        self, 
        db: AsyncSession, 
        rfq: RFQ, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get suppliers recommended for an RFQ using AI matching.
        """
        # Get all supplier companies (excluding RFQ owner)
        result = await db.execute(
            select(Company, User)
            .join(User, Company.id == User.company_id)
            .where(and_(
                User.role == UserRole.SUPPLIER,
                Company.id != rfq.buyer_company_id,
                Company.is_active == True,
                User.is_active == True
            ))
            .distinct()
        )

        suppliers = result.fetchall()
        
        # AI-powered supplier scoring
        recommended_suppliers = []
        rfq_requirements = await self._extract_rfq_requirements(rfq)
        
        for company, user in suppliers:
            supplier_profile = await self._get_supplier_profile_by_company(db, company)
            match_score = await self._calculate_supplier_match_score(rfq_requirements, supplier_profile)
            
            if match_score > 0.4:  # Higher threshold for recommendations
                recommended_suppliers.append({
                    "company": company,
                    "match_score": match_score,
                    "strengths": await self._get_supplier_strengths(supplier_profile, rfq_requirements)
                })
        
        # Sort by match score
        recommended_suppliers.sort(key=lambda x: x["match_score"], reverse=True)
        return recommended_suppliers[:limit]

    async def _get_supplier_profile(self, db: AsyncSession, user: User) -> Dict[str, Any]:
        """Extract supplier profile for matching"""
        company = user.company
        
        # Get recent bids to understand capabilities
        recent_bids = await db.execute(
            select(RFQ.title, RFQ.description)
            .join(RFQ, RFQ.id == user.company.bids[0].rfq_id if user.company.bids else None)
            .limit(5)
        )
        
        return {
            "company_name": company.name,
            "description": company.description or "",
            "location": getattr(company, 'location', ''),
            "website": company.website or "",
            "recent_projects": [bid.title for bid in recent_bids] if recent_bids else [],
            "industries": await self._extract_company_industries(company)
        }

    async def _get_supplier_profile_by_company(self, db: AsyncSession, company: Company) -> Dict[str, Any]:
        """Get supplier profile by company"""
        return {
            "company_name": company.name,
            "description": company.description or "",
            "location": getattr(company, 'location', ''),
            "website": company.website or "",
            "industries": await self._extract_company_industries(company)
        }

    async def _extract_rfq_requirements(self, rfq: RFQ) -> Dict[str, Any]:
        """Extract key requirements from RFQ"""
        return {
            "title": rfq.title,
            "description": rfq.description,
            "requirements": rfq.requirements or "",
            "budget_min": rfq.budget_min,
            "budget_max": rfq.budget_max,
            "deadline": rfq.deadline
        }

    async def _extract_company_industries(self, company: Company) -> List[str]:
        """Extract industries from company description"""
        try:
            if company.description:
                industries = await llm_service.extract_company_industry(company.description)
                return industries
        except:
            pass
        return ["General"]

    async def _calculate_match_score(self, rfq: RFQ, supplier_profile: Dict[str, Any]) -> float:
        """Calculate AI-powered match score between RFQ and supplier"""
        try:
            # Use AI to analyze compatibility
            prompt = f"""
            Rate compatibility (0.0-1.0) between:
            
            RFQ: {rfq.title}
            Description: {rfq.description[:200]}
            
            Supplier: {supplier_profile['company_name']}
            Description: {supplier_profile['description'][:200]}
            
            Return only a number between 0.0 and 1.0:
            """
            
            response = await llm_service.simple_chat(prompt)
            
            # Extract number from response
            import re
            match = re.search(r'0\.\d+|1\.0|0\.0', response)
            if match:
                return float(match.group())
            
        except Exception:
            pass
        
        # Fallback: simple keyword matching
        rfq_text = f"{rfq.title} {rfq.description}".lower()
        supplier_text = f"{supplier_profile['company_name']} {supplier_profile['description']}".lower()
        
        # Simple keyword overlap scoring
        rfq_words = set(rfq_text.split())
        supplier_words = set(supplier_text.split())
        
        if len(rfq_words) == 0:
            return 0.0
        
        overlap = len(rfq_words.intersection(supplier_words))
        return min(overlap / len(rfq_words), 1.0)

    async def _calculate_supplier_match_score(self, rfq_requirements: Dict[str, Any], supplier_profile: Dict[str, Any]) -> float:
        """Calculate how well supplier matches RFQ requirements"""
        return await self._calculate_match_score_simple(rfq_requirements, supplier_profile)

    async def _calculate_match_score_simple(self, rfq_req: Dict[str, Any], supplier: Dict[str, Any]) -> float:
        """Simple fallback matching algorithm"""
        score = 0.0
        
        # Title/description keyword matching
        rfq_text = f"{rfq_req.get('title', '')} {rfq_req.get('description', '')}".lower()
        supplier_text = f"{supplier.get('company_name', '')} {supplier.get('description', '')}".lower()
        
        common_keywords = ['office', 'furniture', 'equipment', 'tech', 'software', 'services', 'supplies']
        
        for keyword in common_keywords:
            if keyword in rfq_text and keyword in supplier_text:
                score += 0.2
        
        return min(score, 1.0)

    async def _get_match_reasons(self, rfq: RFQ, supplier_profile: Dict[str, Any]) -> List[str]:
        """Get reasons why RFQ matches supplier"""
        reasons = []
        
        # Simple keyword-based reasons
        rfq_text = f"{rfq.title} {rfq.description}".lower()
        
        if 'office' in rfq_text and 'furniture' in supplier_profile['description'].lower():
            reasons.append("Office furniture expertise")
        
        if 'tech' in rfq_text and 'technology' in supplier_profile['description'].lower():
            reasons.append("Technology solutions experience")
        
        if rfq.budget_max and rfq.budget_max < 50000:
            reasons.append("Suitable for mid-range budget")
        
        return reasons or ["General capability match"]

    async def _get_supplier_strengths(self, supplier_profile: Dict[str, Any], rfq_requirements: Dict[str, Any]) -> List[str]:
        """Get supplier strengths relevant to RFQ"""
        strengths = []
        
        if supplier_profile.get('website'):
            strengths.append("Established online presence")
        
        if len(supplier_profile.get('description', '')) > 100:
            strengths.append("Detailed company profile")
        
        return strengths or ["Verified supplier"]


# Service instance
matching_service = MatchingService()