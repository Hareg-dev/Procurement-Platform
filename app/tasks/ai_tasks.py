import logging
from typing import Optional

from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.orm import RFQ, Bid
from app.repositories.rfq_repo import rfq_repository
from app.repositories.bid_repo import bid_repository
from app.services.llm_service import llm_service
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="summarize_rfq_and_bids")
def summarize_rfq_and_bids(self, rfq_id: int) -> dict:
    """
    Celery task to generate AI summaries for an RFQ and all its bids.
    
    This task is triggered when:
    1. A new RFQ is created (summarizes the RFQ)
    2. A new bid is submitted (summarizes the new bid and updates RFQ summary)
    
    Args:
        rfq_id: The ID of the RFQ to process
        
    Returns:
        dict: Task result with summary of processed items
    """
    import asyncio
    
    async def _process_summaries():
        """Async function to handle the actual summarization work."""
        try:
            # Get database session
            async for db in get_db():
                # Fetch RFQ with all bids
                rfq = await rfq_repository.get_with_details(db, rfq_id)
                if not rfq:
                    logger.error(f"RFQ {rfq_id} not found")
                    return {"error": f"RFQ {rfq_id} not found"}
                
                results = {
                    "rfq_id": rfq_id,
                    "rfq_summarized": False,
                    "bids_summarized": 0,
                    "errors": []
                }
                
                # Generate RFQ summary if not already present
                if not rfq.ai_summary:
                    try:
                        # Compile RFQ content for summarization
                        rfq_content = f"""
                        Title: {rfq.title}
                        Description: {rfq.description}
                        Budget Range: ${rfq.budget_min or 'Not specified'} - ${rfq.budget_max or 'Not specified'}
                        Deadline: {rfq.deadline}
                        Requirements: {rfq.requirements or 'None specified'}
                        """
                        
                        # Generate AI summary
                        ai_summary = await llm_service.summarize_text(rfq_content.strip())
                        
                        # Update RFQ with summary
                        rfq.ai_summary = ai_summary
                        db.add(rfq)
                        await db.commit()
                        
                        results["rfq_summarized"] = True
                        logger.info(f"Generated AI summary for RFQ {rfq_id}")
                        
                    except Exception as e:
                        error_msg = f"Failed to summarize RFQ {rfq_id}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
                
                # Generate summaries for bids that don't have them
                if rfq.bids:
                    for bid in rfq.bids:
                        if not bid.ai_summary:
                            try:
                                # Compile bid content for summarization
                                bid_content = f"""
                                Price: ${bid.price}
                                Delivery Time: {bid.delivery_time or 'Not specified'} days
                                Message: {bid.message or 'No message provided'}
                                Terms: {bid.terms or 'No specific terms'}
                                Supplier: {bid.supplier_company.name}
                                """
                                
                                # Generate AI summary
                                ai_summary = await llm_service.summarize_text(bid_content.strip())
                                
                                # Update bid with summary
                                bid.ai_summary = ai_summary
                                db.add(bid)
                                await db.commit()
                                
                                results["bids_summarized"] += 1
                                logger.info(f"Generated AI summary for bid {bid.id}")
                                
                            except Exception as e:
                                error_msg = f"Failed to summarize bid {bid.id}: {str(e)}"
                                logger.error(error_msg)
                                results["errors"].append(error_msg)
                
                return results
                
        except Exception as e:
            logger.error(f"Task failed for RFQ {rfq_id}: {str(e)}")
            return {"error": f"Task failed: {str(e)}"}
    
    # Run the async function
    try:
        # Update task state
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"status": f"Processing RFQ {rfq_id}"}
            )
        
        # Execute the async work
        result = asyncio.run(_process_summaries())
        
        logger.info(f"Completed AI summarization task for RFQ {rfq_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Task execution failed for RFQ {rfq_id}: {str(e)}")
        raise


@celery_app.task(bind=True, name="summarize_single_bid")
def summarize_single_bid(self, bid_id: int) -> dict:
    """
    Celery task to generate AI summary for a single bid.
    
    This task is triggered when a new bid is submitted.
    
    Args:
        bid_id: The ID of the bid to summarize
        
    Returns:
        dict: Task result with summary of processing
    """
    import asyncio
    
    async def _process_bid_summary():
        """Async function to handle bid summarization."""
        try:
            # Get database session
            async for db in get_db():
                # Fetch bid with details
                bid = await bid_repository.get_with_details(db, bid_id)
                if not bid:
                    logger.error(f"Bid {bid_id} not found")
                    return {"error": f"Bid {bid_id} not found"}
                
                # Skip if already has summary
                if bid.ai_summary:
                    return {
                        "bid_id": bid_id,
                        "already_summarized": True
                    }
                
                try:
                    # Compile bid content for summarization
                    bid_content = f"""
                    Price: ${bid.price}
                    Delivery Time: {bid.delivery_time or 'Not specified'} days
                    Message: {bid.message or 'No message provided'}
                    Terms: {bid.terms or 'No specific terms'}
                    Supplier: {bid.supplier_company.name}
                    RFQ: {bid.rfq.title}
                    """
                    
                    # Generate AI summary
                    ai_summary = await llm_service.summarize_text(bid_content.strip())
                    
                    # Update bid with summary
                    bid.ai_summary = ai_summary
                    db.add(bid)
                    await db.commit()
                    
                    logger.info(f"Generated AI summary for bid {bid_id}")
                    return {
                        "bid_id": bid_id,
                        "summarized": True
                    }
                    
                except Exception as e:
                    error_msg = f"Failed to summarize bid {bid_id}: {str(e)}"
                    logger.error(error_msg)
                    return {"error": error_msg}
                    
        except Exception as e:
            logger.error(f"Task failed for bid {bid_id}: {str(e)}")
            return {"error": f"Task failed: {str(e)}"}
    
    # Run the async function
    try:
        # Update task state
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"status": f"Processing bid {bid_id}"}
            )
        
        # Execute the async work
        result = asyncio.run(_process_bid_summary())
        
        logger.info(f"Completed AI summarization task for bid {bid_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Task execution failed for bid {bid_id}: {str(e)}")
        raise
