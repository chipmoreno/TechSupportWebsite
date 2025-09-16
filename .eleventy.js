module.exports = function(eleventyConfig) {
  return {
    markdownTemplateEngine: "liquid",
    htmlTemplateEngine: "njk",
    dir: {
      input: "my-blog",
      includes: "_includes",
      output: "_site"
    }
  };
};