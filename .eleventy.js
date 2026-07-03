module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy({ static: "static" });

  return {
    dir: {
      input: "site",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
    pathPrefix: "/stack-watch/",
  };
};
