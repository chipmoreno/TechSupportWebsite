module.exports = function(eleventyConfig) {
  // Pass through the images and other assets
  eleventyConfig.addPassthroughCopy("images");

  // A common pattern is to make Eleventy's collections available to Nunjucks.
  // This is often done implicitly, but it's good practice to be aware of.
  // The 'head' filter should work with this. If not, here's how to add it:
  eleventyConfig.addFilter("head", (array, n) => {
    if( n < 0 ) {
      return array.slice(n);
    }
    return array.slice(0, n);
  });

  return {
    markdownTemplateEngine: "liquid",
    htmlTemplateEngine: "njk",
    dir: {
      input: "my-blog",
      includes: "_includes",
    }
  };
};