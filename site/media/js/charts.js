function bill_chart(container, pro_pct, con_pct, opts) {
	$(function() {
      new Highcharts.Chart({
		chart: {
			backgroundColor: (!opts || !opts.bg) ? "#e8e5df" : opts.bg,
			renderTo: container,
			margin: [0,0,0,0]
		},
		tooltip: {
			enabled: false, //opts && opts.small,
			formatter: function() {
				return this.point.name + "<br>" + this.y + "%";
			}
		},
		credits: { enabled: false },
		plotOptions: {
			pie: {
				animation: false,
				//enableMouseTracking: false,
				stickyTracking: false,
				shadow: false,
				//borderColor: "#8BB6D9",
				borderWidth: 0,
				innerSize: "40%",
				dataLabels: {
					enabled: (opts && opts.labels ? true : false),
					distance: -30,
					formatter: function() {
						return this.point.name + "<br>" + this.y + "%";
					},
					color: 'white',
					style: {
						font: 'bold 14px Verdana, sans-serif'
					}
				}
			}
		},
		colors: ["#71b32b", "#ed5a24"],
		title: { text: null },
		legend: { enabled: false },
		series: [{
			type: "pie",
			data: [["Support", pro_pct], ["Oppose", con_pct]]
		}]
      });
   });
}

function bill_timeseries(container, data, opts) {
	$(function() {
      new Highcharts.Chart({
	 chart: {
	 	backgroundColor: (!opts || !opts.bg) ? "#e8e5df" : opts.bg,
	    renderTo: container,
	    margin: [10,0,(!opts || !opts.xlabels) ? 10 : 65, 70],
	    defaultSeriesType: 'line',
	    width: (!opts || !opts.xlabels) ? 220 : opts.width
	 },
    tooltip: {
    	enabled: (!opts || opts.tooltip == null) ? true : opts.tooltip,
	    formatter: function() {
		    return this.x + ": " + this.y + " " + this.series.name
		}
    },
	 credits: { enabled: false },
	 xAxis: { categories: data.xaxis, labels: { enabled: (!opts || !opts.xlabels) ? false : opts.xlabels, step: 5, rotation: -70, y: 25 } },
	 yAxis: { min: 0, title: { text: "Cumulative Users", style: { fontSize: "10px", fontWeight: "normal" } } },
	 plotOptions: {
		    line: {
		       //enableMouseTracking: false,
			  marker: {
				  enabled: false
			  },
			  stickyTracking: false,
			  dataLabels: {
				enabled: false
			  }
		    }
	    },
		colors: ["#71b32b", "#ed5a24"],
      title: { text: null },
      legend: { enabled: false },
      series: [
	  { name: "Support", data: data.pro},
	  { name: "Oppose", data: data.con},
      ]
     });
   });
}

