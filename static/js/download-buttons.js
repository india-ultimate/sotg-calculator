var export_png = function(e, tab) {
  e.preventDefault();
  e.stopPropagation();
  $(e.target).remove();
  var table = tab.querySelector(".table-responsive");
  domtoimage
    .toPng(tab, { quality: 0.95, bgcolor: "#ffffff", width: table.scrollWidth })
    .then(function(dataUrl) {
      var image_name =
        tab.id
          .split("-")
          .splice(1)
          .join("-") + ".png";
      var link = $("<a>")
        .text("Download")
        .attr("href", dataUrl)
        .attr("download", image_name)
        .appendTo(tab);
    });
};

$(function() {
  // Download button for rankings table
  var table = document.querySelector("#nav-rankings > .table-responsive");

  var score_pages = ["#nav-rankings", "#nav-scores-received", "#nav-scores-awarded"];
  score_pages.forEach(function(selector) {
    var tab = document.querySelector(selector);
    var link = $("<a>")
      .text("Create PNG")
      .attr("href", "#")
      .appendTo(tab)
      .click(function(e) {
        return export_png(e, tab);
      });
  });
});
