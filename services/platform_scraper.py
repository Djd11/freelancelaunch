"""
Live demand data scraper for Upwork, Fiverr, Contra
Uses Playwright for browser automation
"""
import asyncio
import re
import logging
from dataclasses import dataclass
from typing import Optional, List
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


@dataclass
class PlatformDemandData:
    platform: str
    job_count: int
    avg_rate: float
    trend: str
    sample_jobs: List[dict]


class PlatformScraper:
    """Scrape live freelance platform demand data"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        return self
    
    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def scrape_upwork(self, query: str) -> PlatformDemandData:
        """Scrape Upwork job search results"""
        page = await self.browser.new_page()
        try:
            url = f"https://www.upwork.com/nx/search/jobs/?q={query}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            job_count = await self._extract_upwork_job_count(page)
            rates = await self._extract_upwork_rates(page)
            avg_rate = sum(rates) / len(rates) if rates else 0
            sample_jobs = await self._extract_upwork_sample_jobs(page)
            
            return PlatformDemandData(
                platform="upwork",
                job_count=job_count,
                avg_rate=round(avg_rate, 2),
                trend=self._determine_trend(job_count),
                sample_jobs=sample_jobs
            )
        except Exception as e:
            logger.error(f"Upwork scrape failed for '{query}': {e}")
            return PlatformDemandData("upwork", 0, 0, "stable", [])
        finally:
            await page.close()
    
    async def scrape_fiverr(self, query: str) -> PlatformDemandData:
        """Scrape Fiverr gig search"""
        page = await self.browser.new_page()
        try:
            url = f"https://www.fiverr.com/search/gigs?query={query}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            job_count = await self._extract_fiverr_job_count(page)
            rates = await self._extract_fiverr_rates(page)
            avg_rate = sum(rates) / len(rates) if rates else 0
            
            return PlatformDemandData(
                platform="fiverr",
                job_count=job_count,
                avg_rate=round(avg_rate, 2),
                trend=self._determine_trend(job_count),
                sample_jobs=[]
            )
        except Exception as e:
            logger.error(f"Fiverr scrape failed for '{query}': {e}")
            return PlatformDemandData("fiverr", 0, 0, "stable", [])
        finally:
            await page.close()
    
    async def scrape_contra(self, query: str) -> PlatformDemandData:
        """Scrape Contra"""
        page = await self.browser.new_page()
        try:
            url = f"https://contra.com/search?q={query}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            job_count = await self._extract_contra_job_count(page)
            
            return PlatformDemandData(
                platform="contra",
                job_count=job_count,
                avg_rate=0,
                trend=self._determine_trend(job_count),
                sample_jobs=[]
            )
        except Exception as e:
            logger.error(f"Contra scrape failed for '{query}': {e}")
            return PlatformDemandData("contra", 0, 0, "stable", [])
        finally:
            await page.close()
    
    async def _extract_upwork_job_count(self, page) -> int:
        try:
            selectors = [
                "[data-test=job-count]",
                ".job-count",
                "h1:has-text(jobs)",
                "text=/\\d+,?\\d*\\s+jobs?/"
            ]
            for sel in selectors:
                try:
                    text = await page.locator(sel).first.inner_text(timeout=2000)
                    count = self._parse_job_count(text)
                    if count > 0:
                        return count
                except:
                    continue
        except:
            pass
        return 0
    
    async def _extract_upwork_rates(self, page) -> List[float]:
        rates = []
        try:
            cards = await page.locator("[data-test=job-tile], .job-tile").all()
            for card in cards[:10]:
                try:
                    text = await card.inner_text(timeout=1000)
                    rate_matches = re.findall(r"\$(\d+)(?:-(\d+))?\s*/\s*hr", text)
                    for match in rate_matches:
                        low = int(match[0])
                        high = int(match[1]) if match[1] else low
                        rates.append((low + high) / 2)
                except:
                    continue
        except:
            pass
        return rates
    
    async def _extract_upwork_sample_jobs(self, page) -> List[dict]:
        jobs = []
        try:
            cards = await page.locator("[data-test=job-tile], .job-tile").all()
            for card in cards[:3]:
                try:
                    title = await card.locator("h3, [data-test=job-title], a").first.inner_text(timeout=1000)
                    jobs.append({"title": title.strip()[:100]})
                except:
                    continue
        except:
            pass
        return jobs
    
    async def _extract_fiverr_job_count(self, page) -> int:
        try:
            selectors = [
                "[data-testid=search-results-count]",
                ".search-results-count",
                "text=/\\d+,?\\d*\s+(gigs?|services?|results?)/i"
            ]
            for sel in selectors:
                try:
                    text = await page.locator(sel).first.inner_text(timeout=2000)
                    count = self._parse_job_count(text)
                    if count > 0:
                        return count
                except:
                    continue
        except:
            pass
        return 0
    
    async def _extract_fiverr_rates(self, page) -> List[float]:
        rates = []
        try:
            cards = await page.locator("[data-testid=gig-card], .gig-card").all()
            for card in cards[:10]:
                try:
                    text = await card.inner_text(timeout=1000)
                    matches = re.findall(r"(?:From\s+)?\$(\d+)", text)
                    for m in matches[:1]:
                        rates.append(int(m))
                except:
                    continue
        except:
            pass
        return rates
    
    async def _extract_contra_job_count(self, page) -> int:
        try:
            count = await page.locator("[data-cy=project-card], .project-card").count()
            if count > 0:
                return count
            text = await page.locator("body").inner_text(timeout=2000)
            return self._parse_job_count(text)
        except:
            pass
        return 0
    
    def _parse_job_count(self, text: str) -> int:
        if not text:
            return 0
        clean = text.replace(",", "")
        matches = re.findall(r"\d+", clean)
        if matches:
            return max(int(m) for m in matches)
        return 0
    
    def _determine_trend(self, job_count: int) -> str:
        if job_count > 500:
            return "growing"
        if job_count > 100:
            return "stable"
        return "declining"


async def scrape_all_platforms(query: str) -> dict:
    """Convenience function to scrape all platforms"""
    async with PlatformScraper() as scraper:
        upwork_task = scraper.scrape_upwork(query)
        fiverr_task = scraper.scrape_fiverr(query)
        contra_task = scraper.scrape_contra(query)
        
        upwork, fiverr, contra = await asyncio.gather(
            upwork_task, fiverr_task, contra_task, return_exceptions=True
        )
        
        results = {}
        for platform, data in [("upwork", upwork), ("fiverr", fiverr), ("contra", contra)]:
            if isinstance(data, Exception):
                logger.error(f"{platform} scrape failed: {data}")
                results[platform] = None
            else:
                results[platform] = data
        
        return results