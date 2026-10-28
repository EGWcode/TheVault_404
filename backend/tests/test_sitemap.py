""" By Jaylen Belle - 10/21/2026 """



import os
import sys
import unittest



#lets the file find app.py 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app



class TestSitemapPage(unittest.TestCase):

    """this runs once before the test and then starts a test version of the site and open /sitemap """
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()  #creats a fake browser to test
        cls.response = cls.client.get("sitemap")
        cls.html = cls.response.get_data(as_text = True)


    """Test to see if the sitemap page opens with an error"""
    def test_page_oads(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertIn("Campus Sitemap", self.html)


    """this test that the page has everything that sitemap.js looks for by id"""
    def test_page_has_all_parts(self):
        for part in ["campusMap", "placeList", "placeSearch", "placeDetails", "pickReadout"]:
            self.assertIn(f'id="{part}"', self.html)


    """This checks if the page has the three filter buttons"""
    def test_page_has_filter_buttons(self):
        for name in ["all", "meetup", "building"]:
            self.assertIn(f'data-filter="{name}"', self.html)


    """ tests to see if the back button goes back to storefront"""
    def test_back_button(self):
        self.assertIn('href="/storefront"', self.html)

    """Test to see if the sitemap.css, sitemap.js and the map picture actually load and linked to the page"""
    def test_files_load(self):
        for file in ["/static/css/sitemap.css", "/static/js/campus_locations.js", "/static/js/sitemap.js", "/static/images/campus_map.jpg"]:
            self.assertIn(file, self.html)
            response = self.client.get(file)
            self.assertEqual(response.status_code, 200,f"{file} did not load")
            response.close()


    """tests if the campus_locations loads beofre sitemap.js because it uses the lists from campus_locations. """
    def test_data_loads_first(self):
        self.assertLess(self.html.index("js/campus_locations.js"), self.html.index("js/sitemap.js"))


    """makes sure the button on the homepage points to /sitemap"""
    def test_menu_link(self):
        page = self.client.get("/storefront").get_data(as_text = True)
        self.assertIn('href="/sitemap"', page)


if __name__=="__main__":
    unittest.main(verbosity=2)